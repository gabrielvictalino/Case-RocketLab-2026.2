"""Limites de uso do LLM por usuário, no Redis (seção 10 do system design).

- Janela deslizante por usuário e rota em `rl:{usuario}:{rota}`: um sorted set com o
  instante de cada chamada que passou. Uma chamada barrada não entra na janela.
- Cota diária de tokens por usuário em `cota:{usuario}:{AAAA-MM-DD}`. Antes do LLM, a
  pergunta reserva uma estimativa num passo só (confere o saldo e já debita); no fim,
  a reserva vira o gasto real, também numa pergunta que falhou. Assim, perguntas
  simultâneas do mesmo usuário não passam com o mesmo saldo. O dia vira à meia-noite
  de Recife.

Os dois são fail-open: se o Redis cair ou não responder a tempo, a pergunta segue, e o
limite por IP do Nginx continua valendo. Quem tem cache (os insights) chama `consumir` e
reserva a cota só quando vai ao LLM: um cache hit não gasta o limite.
"""

import asyncio
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from redis.exceptions import RedisError

from app.core.errors import APIError

JANELA_S = 60
# Recife não tem horário de verão.
FUSO = timezone(timedelta(hours=-3))
TTL_COTA_S = 2 * 24 * 60 * 60

# Uma falha do Redis, inclusive o TimeoutError nativo que não vem embrulhado em RedisError
# (TimeoutError herda de OSError), deixa o limite aberto, em vez de responder 500.
FALHAS_DO_REDIS = (RedisError, OSError)

# Confere o saldo e debita a reserva no mesmo passo: uma segunda pergunta já vê o saldo
# da primeira, ainda em andamento. Devolve {1, usados} quando reservou e {0, usados}
# quando a cota do dia acabou: o status vem separado do contador. Um contador negativo
# (a chave apagada à mão, ou perdida entre a reserva e o acerto) conta como zero.
RESERVAR = """
local usados = tonumber(redis.call('GET', KEYS[1]) or '0')
if usados < 0 then
  usados = 0
  redis.call('SET', KEYS[1], 0, 'EX', ARGV[3])
end
if usados >= tonumber(ARGV[1]) then
  return {0, usados}
end
redis.call('INCRBY', KEYS[1], ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return {1, usados}
"""

# Troca a reserva pelo gasto real sem deixar o contador negativo: se a chave sumiu entre
# a reserva e o acerto, a diferença negativa não vira crédito para o dia.
ACERTAR = """
local usados = redis.call('INCRBY', KEYS[1], ARGV[1])
if usados < 0 then
  redis.call('SET', KEYS[1], 0)
end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return usados
"""

logger = logging.getLogger('venergy.limites')


@dataclass(frozen=True)
class Reserva:
    """Tokens debitados da cota antes do LLM. Zero quando o Redis não respondeu."""

    # A chave do dia da reserva: a pergunta que vira a meia-noite acerta o dia em que entrou.
    chave: str
    tokens: int


async def consumir(
    redis,
    usuario_id,
    rota: str,
    limite: int,
    agora: float | None = None,
    rotulo: str = 'perguntas',
    codigo: str = 'LIMITE_DE_PERGUNTAS',
):
    """Conta uma chamada na janela de 1 minuto; acima do limite, responde 429.

    `rotulo` e `codigo` dizem o que foi limitado: quem abre a Visão Geral não fez pergunta."""
    chave = f'rl:{usuario_id}:{rota}'
    agora = time.time() if agora is None else agora
    membro = f'{agora:.6f}:{uuid4().hex}'
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.zremrangebyscore(chave, 0, agora - JANELA_S)
            pipe.zadd(chave, {membro: agora})
            pipe.zcard(chave)
            pipe.zrange(chave, 0, 0, withscores=True)
            pipe.expire(chave, JANELA_S)
            _, _, total, [(_, mais_antiga)], _ = await pipe.execute()
        if total <= limite:
            return
        await redis.zrem(chave, membro)
    except FALHAS_DO_REDIS:
        logger.warning('rota=%s redis indisponível; limite por usuário não aplicado', rota)
        return
    espera = max(1, math.ceil(mais_antiga + JANELA_S - agora))
    raise APIError(
        429,
        f'Limite de {limite} {rotulo} por minuto atingido. Tente de novo em {espera} s.',
        codigo,
        headers={'Retry-After': str(espera)},
    )


async def reservar_cota(
    redis, usuario_id, cota: int, reserva: int, agora: float | None = None
) -> Reserva:
    """Debita `reserva` tokens da cota do dia antes do LLM. Responde 429 até a meia-noite
    quando o usuário já gastou, ou já reservou em outra pergunta, a cota do dia."""
    agora = time.time() if agora is None else agora
    chave = _chave_cota(usuario_id, agora)
    try:
        reservou, _ = await redis.eval(RESERVAR, 1, chave, cota, reserva, TTL_COTA_S)
    except FALHAS_DO_REDIS:
        logger.warning('redis indisponível; cota de tokens não conferida')
        return Reserva(chave, 0)
    if reservou:
        return Reserva(chave, reserva)
    hoje = datetime.fromtimestamp(agora, FUSO)
    amanha = datetime.combine(hoje.date() + timedelta(days=1), datetime.min.time(), FUSO)
    espera = max(1, math.ceil(amanha.timestamp() - agora))
    raise APIError(
        429,
        'A cota diária de tokens do assistente acabou. Ela volta à meia-noite.',
        'COTA_DE_TOKENS_ESGOTADA',
        headers={'Retry-After': str(espera)},
    )


async def acertar_cota(redis, reserva: Reserva, gastos: int):
    """Troca a reserva pelos tokens que a pergunta gastou de fato.

    Roda blindado: quem chama costuma estar num `finally` de uma pergunta cancelada, e o
    cancel scope do middleware HTTP (anyio) cancela de novo a cada `await`. Sem a
    blindagem, o acerto morreria no primeiro `await` e a reserva ficaria cobrada até a
    meia-noite: umas 25 perguntas abandonadas esgotariam a cota do dia."""
    diferenca = gastos - reserva.tokens
    if diferenca == 0:
        return
    await asyncio.shield(_acertar(redis, reserva.chave, diferenca))


async def _acertar(redis, chave: str, diferenca: int):
    try:
        await redis.eval(ACERTAR, 1, chave, diferenca, TTL_COTA_S)
    except FALHAS_DO_REDIS:
        logger.warning('redis indisponível; cota não acertada em %s tokens', diferenca)


def _chave_cota(usuario_id, agora: float) -> str:
    return f'cota:{usuario_id}:{datetime.fromtimestamp(agora, FUSO):%Y-%m-%d}'
