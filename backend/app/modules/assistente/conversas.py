"""Estado das conversas do agente no Redis, para os follow-ups.

`conversa:{id}` guarda a dona e `conversa:{id}:trocas`, a lista das últimas trocas
(pergunta, métrica, filtros, período e SQL), da mais antiga para a mais recente. As duas
chaves têm TTL de 2 h, renovado a cada pergunta. O histórico permanente fica na
auditoria. É fail-open: sem Redis, a pergunta segue sem o histórico.
"""

import logging

from redis.exceptions import RedisError
from venergy_ai.interface import TROCAS_NA_CONVERSA, RespostaAgente, Troca

TTL_S = 2 * 60 * 60

# Acrescenta a troca ao que está no Redis agora, num passo só. Duas perguntas ao mesmo
# tempo na mesma conversa não partem da mesma lista lida antes do LLM, e uma não apaga
# a troca da outra.
ACRESCENTAR = """
local dona = redis.call('GET', KEYS[1])
if dona and dona ~= ARGV[1] then
  return 0
end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[4])
redis.call('RPUSH', KEYS[2], ARGV[2])
redis.call('LTRIM', KEYS[2], -tonumber(ARGV[3]), -1)
redis.call('EXPIRE', KEYS[2], ARGV[4])
return 1
"""

logger = logging.getLogger('venergy.assistente')


def chave(conversa_id) -> str:
    return f'conversa:{conversa_id}'


def chave_das_trocas(conversa_id) -> str:
    return f'conversa:{conversa_id}:trocas'


async def ler(redis, conversa_id, usuario_id) -> list[Troca]:
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.get(chave(conversa_id))
            pipe.lrange(chave_das_trocas(conversa_id), 0, -1)
            dona, trocas = await pipe.execute()
    except RedisError:
        logger.warning('conversa=%s redis indisponível; pergunta sem histórico', conversa_id)
        return []
    # A dona da conversa já foi conferida na auditoria; aqui é só uma segunda trava.
    if dona is None or dona.decode() != str(usuario_id):
        return []
    return [Troca.model_validate_json(troca) for troca in trocas]


async def registrar(redis, conversa_id, usuario_id, pergunta, resposta):
    """Acrescenta a troca respondida. Uma resposta sem métrica (fora do domínio, por exemplo)
    não muda o estado que o próximo follow-up herda."""
    if resposta.metrica is None:
        return
    troca = _troca(pergunta, resposta).model_dump_json()
    chaves = (chave(conversa_id), chave_das_trocas(conversa_id))
    try:
        await redis.eval(
            ACRESCENTAR, len(chaves), *chaves, str(usuario_id), troca, TROCAS_NA_CONVERSA, TTL_S
        )
    except RedisError:
        logger.warning('conversa=%s redis indisponível; troca não guardada', conversa_id)


def _troca(pergunta: str, resposta: RespostaAgente) -> Troca:
    ultima = resposta.consultas[-1] if resposta.consultas else None
    return Troca(
        pergunta=pergunta,
        metrica=resposta.metrica,
        filtros=resposta.filtros,
        periodo=resposta.periodo,
        sql=ultima and ultima.sql_executado,
    )
