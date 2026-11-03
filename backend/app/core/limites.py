"""Limites de uso do LLM por usuário, no Redis (seção 10 do system design).

- Janela deslizante por usuário e rota em `rl:{usuario}:{rota}`: um sorted set com o
  instante de cada chamada que passou. Uma chamada barrada não entra na janela.
- Cota diária de tokens por usuário em `cota:{usuario}:{AAAA-MM-DD}`, somada depois de
  cada pergunta, também das que falham. O dia vira à meia-noite de Recife.

Os dois são fail-open: se o Redis cair, a pergunta segue, e o limite por IP do Nginx
continua valendo. Quem tem cache (os insights) chama `consumir` só quando vai ao LLM:
um cache hit não gasta o limite.
"""

import logging
import math
import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from redis.exceptions import RedisError

from app.core.errors import APIError

JANELA_S = 60
# Recife não tem horário de verão.
FUSO = timezone(timedelta(hours=-3))
TTL_COTA_S = 2 * 24 * 60 * 60

logger = logging.getLogger('venergy.limites')


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
    except RedisError:
        logger.warning('rota=%s redis indisponível; limite por usuário não aplicado', rota)
        return
    espera = max(1, math.ceil(mais_antiga + JANELA_S - agora))
    raise APIError(
        429,
        f'Limite de {limite} perguntas por minuto atingido. Tente de novo em {espera} s.',
        'LIMITE_DE_PERGUNTAS',
        headers={'Retry-After': str(espera)},
    )


async def conferir_cota(redis, usuario_id, cota: int, agora: float | None = None):
    """Responde 429 até a meia-noite quando o usuário já gastou a cota de tokens do dia."""
    agora = time.time() if agora is None else agora
    try:
        usados = int(await redis.get(_chave_cota(usuario_id, agora)) or 0)
    except RedisError:
        logger.warning('redis indisponível; cota de tokens não conferida')
        return
    if usados < cota:
        return
    hoje = datetime.fromtimestamp(agora, FUSO)
    amanha = datetime.combine(hoje.date() + timedelta(days=1), datetime.min.time(), FUSO)
    espera = max(1, math.ceil(amanha.timestamp() - agora))
    raise APIError(
        429,
        'A cota diária de tokens do assistente acabou. Ela volta à meia-noite.',
        'COTA_DE_TOKENS_ESGOTADA',
        headers={'Retry-After': str(espera)},
    )


async def gastar_tokens(redis, usuario_id, tokens: int, agora: float | None = None):
    if tokens <= 0:
        return
    chave = _chave_cota(usuario_id, time.time() if agora is None else agora)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incrby(chave, tokens)
            pipe.expire(chave, TTL_COTA_S)
            await pipe.execute()
    except RedisError:
        logger.warning('redis indisponível; %s tokens não somados à cota', tokens)


def _chave_cota(usuario_id, agora: float) -> str:
    return f'cota:{usuario_id}:{datetime.fromtimestamp(agora, FUSO):%Y-%m-%d}'
