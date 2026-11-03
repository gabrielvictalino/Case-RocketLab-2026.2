import asyncio
import time
from uuid import uuid4

from venergy_ai.agente import AgenteTextoSQL
from venergy_ai.executor import ExecutorAiRead
from venergy_ai.interface import Assistente, Contexto, ProvedorIndisponivel, RespostaAgente
from venergy_ai.modelo import criar_modelo
from venergy_ai.semantica import Periodo

from app.core.errors import APIError
from app.core.periodos import validar_periodos
from app.modules.assistente import repository
from app.modules.assistente.schemas import Auditoria, Pergunta, RespostaPergunta
from app.modules.meta import repository as meta


def criar_assistente(settings, ai_engine) -> Assistente | None:
    """O agente recebe só a engine da role ai_read; a do portal fica com a auditoria."""
    chave = {'google': settings.gemini_api_key, 'openrouter': settings.openrouter_api_key}[
        settings.ai_provedor
    ]
    if chave is None or not chave.get_secret_value():
        return None
    modelo = criar_modelo(settings.ai_provedor, settings.ai_modelo, chave.get_secret_value())
    return AgenteTextoSQL(modelo, ExecutorAiRead(ai_engine))


async def perguntar(state, body: Pergunta, usuario) -> RespostaPergunta:
    if state.assistente is None:
        raise APIError(503, 'Assistente não configurado neste ambiente', 'ASSISTENTE_INDISPONIVEL')
    # Sessões curtas do portal antes e depois do agente: nenhuma conexão do portal fica
    # presa enquanto o modelo responde, e as rotas das telas seguem com o pool livre.
    async with state.portal_sessions() as db, db.begin():
        carga = await meta.carga_atual(db)
        if body.conversa_id is not None:
            dono = await repository.dono_da_conversa(db, body.conversa_id)
            if dono != usuario['id']:
                raise APIError(404, 'Conversa não encontrada', 'CONVERSA_NAO_ENCONTRADA')
    if carga is None:
        raise APIError(503, 'Nenhuma carga publicada; execute o importador', 'BASE_INDISPONIVEL')
    contexto = _contexto(body, carga)
    registro = dict(
        id=uuid4(),
        conversa_id=body.conversa_id or uuid4(),
        usuario_id=usuario['id'],
        pergunta=body.pergunta,
        contexto=body.contexto.model_dump(mode='json'),
        consultas=[],
        nao_sei=False,
    )
    inicio = time.monotonic()
    try:
        async with asyncio.timeout(state.settings.assistente_timeout_s):
            resposta = await state.assistente.responder(body.pergunta, contexto)
    except TimeoutError:
        await _registrar_falha(state, registro, inicio, 'TEMPO_ESGOTADO')
        raise APIError(
            503, 'O assistente demorou demais para responder', 'ASSISTENTE_TEMPO_ESGOTADO'
        ) from None
    except ProvedorIndisponivel as erro:
        await _registrar_falha(state, registro, inicio, f'PROVEDOR_INDISPONIVEL: {erro}')
        raise APIError(
            503, 'O provedor do modelo está indisponível', 'PROVEDOR_INDISPONIVEL'
        ) from None
    async with state.portal_sessions() as db, db.begin():
        await repository.registrar(db, registro | _da_resposta(resposta))
    return RespostaPergunta(
        **resposta.model_dump(), id_resposta=registro['id'], conversa_id=registro['conversa_id']
    )


async def auditoria(db, id_resposta, usuario) -> Auditoria:
    linha = await repository.obter(db, id_resposta)
    if linha is None:
        raise APIError(404, 'Resposta não encontrada', 'RESPOSTA_NAO_ENCONTRADA')
    if linha['usuario_id'] != usuario['id'] and usuario['cargo'] != 'diretoria':
        raise APIError(
            403, 'Só o autor da pergunta ou a diretoria veem a auditoria', 'SEM_PERMISSAO'
        )
    return Auditoria(**linha)


def _contexto(body: Pergunta, carga) -> Contexto:
    pedido = body.contexto
    periodo = comparacao = None
    if pedido.periodo is not None:
        atual, anterior = validar_periodos(
            pedido.periodo,
            pedido.comparacao,
            carga['competencia_inicial'],
            carga['competencia_mais_recente'],
        )
        periodo = Periodo(atual.inicio, atual.fim)
        comparacao = anterior and Periodo(anterior.inicio, anterior.fim)
    elif pedido.comparacao is not None:
        raise APIError(422, 'Informe periodo junto com comparacao', 'PERIODO_INVALIDO')
    return Contexto(
        competencia_mais_recente=carga['competencia_mais_recente'],
        tela=pedido.tela,
        periodo=periodo,
        comparacao=comparacao,
        recortes=pedido.recortes,
    )


def _da_resposta(resposta: RespostaAgente) -> dict:
    # A última tentativa é a que sustenta a resposta; todas ficam em consultas.
    ultima = resposta.consultas[-1] if resposta.consultas else None
    return dict(
        consultas=[c.model_dump(mode='json') for c in resposta.consultas],
        sql_gerado=ultima and ultima.sql_gerado,
        sql_executado=ultima and ultima.sql_executado,
        numero_linhas=ultima and ultima.total_linhas,
        resposta=resposta.texto,
        nao_sei=resposta.tipo == 'nao_sei',
        motivo=resposta.motivo,
        modelo=resposta.modelo,
        tokens_entrada=resposta.tokens_entrada,
        tokens_saida=resposta.tokens_saida,
        latencia_ms=resposta.latencia_ms,
    )


async def _registrar_falha(state, registro, inicio, erro):
    latencia = round((time.monotonic() - inicio) * 1000)
    async with state.portal_sessions() as db, db.begin():
        await repository.registrar(db, registro | dict(latencia_ms=latencia, erro=erro))
