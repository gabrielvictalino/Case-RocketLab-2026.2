"""Estado das conversas do agente no Redis, para os follow-ups.

`conversa:{id}` guarda o dono e as últimas trocas (pergunta, métrica, filtros, período e
SQL), com TTL de 2 h renovado a cada pergunta. O histórico permanente fica na auditoria.
É fail-open: sem Redis, a pergunta segue sem o histórico.
"""

import json
import logging

from redis.exceptions import RedisError
from venergy_ai.interface import TROCAS_NA_CONVERSA, RespostaAgente, Troca

TTL_S = 2 * 60 * 60

logger = logging.getLogger('venergy.assistente')


def chave(conversa_id) -> str:
    return f'conversa:{conversa_id}'


async def ler(redis, conversa_id, usuario_id) -> list[Troca]:
    try:
        bruto = await redis.get(chave(conversa_id))
    except RedisError:
        logger.warning('conversa=%s redis indisponível; pergunta sem histórico', conversa_id)
        return []
    if bruto is None:
        return []
    estado = json.loads(bruto)
    # A dona da conversa já foi conferida na auditoria; aqui é só uma segunda trava.
    if estado.get('usuario_id') != str(usuario_id):
        return []
    return [Troca.model_validate(troca) for troca in estado['trocas']]


async def registrar(redis, conversa_id, usuario_id, historico, pergunta, resposta):
    """Acrescenta a troca respondida. Uma resposta sem métrica (fora do domínio, por exemplo)
    não muda o estado que o próximo follow-up herda."""
    if resposta.metrica is None:
        return
    trocas = [*historico, _troca(pergunta, resposta)][-TROCAS_NA_CONVERSA:]
    estado = {'usuario_id': str(usuario_id), 'trocas': [t.model_dump(mode='json') for t in trocas]}
    try:
        await redis.set(chave(conversa_id), json.dumps(estado, ensure_ascii=False), ex=TTL_S)
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
