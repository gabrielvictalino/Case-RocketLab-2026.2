"""Limites de uso do LLM por usuário, no Redis (seção 10 do system design).

- Janela deslizante por usuário e rota em `rl:{usuario}:{rota}`: um sorted set com o
  instante de cada chamada que passou. Uma chamada barrada não entra na janela.
- Cota diária de tokens por usuário em `cota:{usuario}:{AAAA-MM-DD}`. Antes do LLM, a
  pergunta reserva uma estimativa num passo só (confere o saldo e já debita); no fim,
  a reserva vira o gasto real, também numa pergunta que falhou. Assim, perguntas
  simultâneas do mesmo usuário não passam com o mesmo saldo. O dia vira à meia-noite
  de Recife. Cada reserva tem um id, e o valor debitado fica em
  `cota-reservas:{usuario}:{AAAA-MM-DD}`: o acerto desconta o que o Redis debitou de
  fato, uma vez só, mesmo quando a resposta da reserva se perdeu num timeout.

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
# (a chave apagada à mão, ou perdida entre a reserva e o acerto) conta como zero. O valor
# debitado fica no hash das reservas, pelo id da reserva, para o acerto descontá-lo.
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
redis.call('HSET', KEYS[2], ARGV[4], ARGV[2])
redis.call('EXPIRE', KEYS[2], ARGV[3])
return {1, usados}
"""

# Troca a reserva pelo gasto real sem deixar o contador negativo: se a chave sumiu entre
# a reserva e o acerto, a diferença negativa não vira crédito para o dia. Desconta o que
# o hash diz que a reserva debitou (zero se ela não chegou a debitar) e apaga a entrada:
# um segundo acerto da mesma reserva não desconta de novo.
ACERTAR = """
local reservado = tonumber(redis.call('HGET', KEYS[2], ARGV[3]) or '0')
redis.call('HDEL', KEYS[2], ARGV[3])
local diferenca = tonumber(ARGV[1]) - reservado
if diferenca == 0 then
  return tonumber(redis.call('GET', KEYS[1]) or '0')
end
local usados = redis.call('INCRBY', KEYS[1], diferenca)
if usados < 0 then
  redis.call('SET', KEYS[1], 0)
end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return usados
"""

logger = logging.getLogger('venergy.limites')


@dataclass(frozen=True)
class Reserva:
    """Tokens debitados da cota antes do LLM. Zero quando o Redis não respondeu; nesse
    caso, o débito pode ter acontecido mesmo assim, e o acerto confere pelo id."""

    # A chave do dia da reserva: a pergunta que vira a meia-noite acerta o dia em que entrou.
    chave: str
    tokens: int
    # Identifica a reserva no hash das reservas do dia.
    id: str = ''


async def consumir(redis, usuario_id, rota: str, limite: int, agora: float | None = None):
    """Conta uma chamada na janela de 1 minuto; acima do limite, responde 429."""
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
        f'Limite de {limite} perguntas por minuto atingido. Tente de novo em {espera} s.',
        'LIMITE_DE_PERGUNTAS',
        headers={'Retry-After': str(espera)},
    )


async def reservar_cota(
    redis, usuario_id, cota: int, reserva: int, agora: float | None = None
) -> Reserva:
    """Debita `reserva` tokens da cota do dia antes do LLM. Responde 429 até a meia-noite
    quando o usuário já gastou, ou já reservou em outra pergunta, a cota do dia."""
    agora = time.time() if agora is None else agora
    chave, id_reserva = _chave_cota(usuario_id, agora), uuid4().hex
    try:
        reservou, _ = await redis.eval(
            RESERVAR, 2, chave, _chave_reservas(chave), cota, reserva, TTL_COTA_S, id_reserva
        )
    except FALHAS_DO_REDIS:
        # O Redis pode ter debitado antes de a resposta se perder: o acerto confere pelo id.
        logger.warning('redis indisponível; cota de tokens não conferida')
        return Reserva(chave, 0, id_reserva)
    if reservou:
        return Reserva(chave, reserva, id_reserva)
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
    meia-noite: umas 25 perguntas abandonadas esgotariam a cota do dia.

    Roda também quando a reserva voltou com zero: se ela debitou e a resposta se perdeu
    num timeout, o acerto desconta o débito que o Redis registrou."""
    await asyncio.shield(_acertar(redis, reserva, gastos))


async def _acertar(redis, reserva: Reserva, gastos: int):
    try:
        await redis.eval(
            ACERTAR,
            2,
            reserva.chave,
            _chave_reservas(reserva.chave),
            gastos,
            TTL_COTA_S,
            reserva.id,
        )
    except FALHAS_DO_REDIS:
        logger.warning('redis indisponível; cota não acertada em %s tokens', gastos)


def _chave_cota(usuario_id, agora: float) -> str:
    return f'cota:{usuario_id}:{datetime.fromtimestamp(agora, FUSO):%Y-%m-%d}'


def _chave_reservas(chave_cota: str) -> str:
    return 'cota-reservas:' + chave_cota.removeprefix('cota:')
