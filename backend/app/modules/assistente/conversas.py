"""Estado das conversas do agente no Redis, para os follow-ups.

`conversa:v2:{id}` guarda a dona e `conversa:v2:{id}:trocas`, a lista das últimas trocas
(pergunta, métrica, filtros, período, SQL e o período da tela), da mais antiga para a
mais recente. As duas chaves têm TTL de 2 h, renovado a cada pergunta, na leitura e na
gravação. O histórico permanente fica na auditoria. É fail-open: sem Redis, a pergunta
segue sem o histórico, e uma troca que não se lê mais fica fora dele.

O `v2` separa este formato do anterior, em que `conversa:{id}` era um JSON só com a
dona e as trocas. Uma conversa aberta antes do deploy continua como conversa nova, sem
o histórico de antes, e as chaves antigas expiram sozinhas em até 2 h.
"""

import logging

from pydantic import ValidationError
from app.core.limites import FALHAS_DO_REDIS
from venergy_ai.interface import TROCAS_NA_CONVERSA, Consulta, RespostaAgente, Troca
from venergy_ai.semantica import Periodo

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
    return f'conversa:v2:{conversa_id}'


def chave_das_trocas(conversa_id) -> str:
    return f'conversa:v2:{conversa_id}:trocas'


async def ler(redis, conversa_id, usuario_id) -> list[Troca]:
    """As trocas da conversa. A leitura também renova o TTL: uma sequência de perguntas
    fora do domínio, ou que falham, não deixa a conversa expirar no meio do uso."""
    chaves = (chave(conversa_id), chave_das_trocas(conversa_id))
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.get(chaves[0])
            pipe.lrange(chaves[1], 0, -1)
            for chave_redis in chaves:
                pipe.expire(chave_redis, TTL_S)
            dona, trocas, *_ = await pipe.execute()
    except FALHAS_DO_REDIS:
        logger.warning('conversa=%s redis indisponível; pergunta sem histórico', conversa_id)
        return []
    # A dona da conversa já foi conferida na auditoria; aqui é só uma segunda trava.
    if dona is None or dona.decode() != str(usuario_id):
        return []
    legiveis = []
    for troca in trocas:
        try:
            legiveis.append(Troca.model_validate_json(troca))
        except ValidationError:
            # Uma troca gravada por outra versão de Troca não derruba a pergunta: ela fica
            # de fora, e a lista a descarta sozinha depois de 5 trocas novas.
            logger.warning(
                'conversa=%s troca ilegível no redis; fica fora do histórico', conversa_id
            )
    return legiveis


async def registrar(
    redis, conversa_id, usuario_id, pergunta, resposta, periodo_da_tela: Periodo | None
):
    """Acrescenta a troca respondida. Uma resposta sem consulta que rodou com sucesso (fora
    do domínio, ou com o SQL falhando no banco em todas as tentativas) não muda o estado
    que o próximo follow-up herda. Uma com consulta bem-sucedida entra mesmo sem métrica,
    que a conferência pode ter descartado por citar um número sem lastro: os filtros, o
    período e o SQL dela ainda valem para "e em 2024?".
    `periodo_da_tela` é o da pergunta: se a tela mudar de período depois, a próxima
    pergunta sem período usa o da tela."""
    if resposta.metrica is None and _consulta_bem_sucedida(resposta) is None:
        return
    troca = _troca(pergunta, resposta, periodo_da_tela).model_dump_json()
    chaves = (chave(conversa_id), chave_das_trocas(conversa_id))
    try:
        await redis.eval(
            ACRESCENTAR, len(chaves), *chaves, str(usuario_id), troca, TROCAS_NA_CONVERSA, TTL_S
        )
    except FALHAS_DO_REDIS:
        logger.warning('conversa=%s redis indisponível; troca não guardada', conversa_id)


def _consulta_bem_sucedida(resposta: RespostaAgente) -> Consulta | None:
    """A última consulta que rodou sem erro. Uma que a guarda rejeitou não tem
    `sql_executado`; uma que falhou no banco tem, mas também tem `erro`."""
    for consulta in reversed(resposta.consultas):
        if consulta.sql_executado and consulta.erro is None:
            return consulta
    return None


def _troca(pergunta: str, resposta: RespostaAgente, periodo_da_tela: Periodo | None) -> Troca:
    # O follow-up parte do SQL que rodou, nunca de uma tentativa que falhou.
    consulta = _consulta_bem_sucedida(resposta)
    return Troca(
        pergunta=pergunta,
        metrica=resposta.metrica,
        filtros=resposta.filtros,
        periodo=resposta.periodo,
        sql=consulta and consulta.sql_executado,
        periodo_da_tela=periodo_da_tela,
    )
