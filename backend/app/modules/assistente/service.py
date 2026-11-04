import asyncio
import time
from uuid import uuid4

from pydantic_ai.models import Model
from venergy_ai.agente import AgenteTextoSQL
from venergy_ai.executor import ExecutorAiRead
from venergy_ai.interface import (
    Andamento,
    Assistente,
    BancoIndisponivel,
    Consulta,
    Contexto,
    ProvedorIndisponivel,
    RespostaAgente,
    Troca,
)
from venergy_ai.modelo import criar_modelo
from venergy_ai.semantica import Periodo

from app.core import limites
from app.core.errors import APIError
from app.core.periodos import validar_periodos
from app.modules.assistente import conversas, repository
from app.modules.assistente.schemas import (
    TELAS,
    Auditoria,
    Conversa,
    Pergunta,
    RespostaPergunta,
)
from app.modules.meta import repository as meta


def modelo_configurado(settings) -> Model | None:
    """O modelo do provedor escolhido. Sem a chave dele, não há modelo e a IA responde 503."""
    chave = {'google': settings.gemini_api_key, 'openrouter': settings.openrouter_api_key}[
        settings.ai_provedor
    ]
    if chave is None or not chave.get_secret_value():
        return None
    return criar_modelo(settings.ai_provedor, settings.ai_modelo, chave.get_secret_value())


def criar_assistente(settings, ai_engine) -> Assistente | None:
    """O agente recebe só a engine da role ai_read; a do portal fica com a auditoria."""
    modelo = modelo_configurado(settings)
    return None if modelo is None else AgenteTextoSQL(modelo, ExecutorAiRead(ai_engine))


async def perguntar(state, body: Pergunta, usuario) -> RespostaPergunta:
    if state.assistente is None:
        raise APIError(503, 'Assistente não configurado neste ambiente', 'ASSISTENTE_INDISPONIVEL')
    settings = state.settings
    await limites.conferir_cota(state.redis, usuario['id'], settings.assistente_cota_tokens_dia)
    await limites.consumir(
        state.redis, usuario['id'], 'assistente', settings.assistente_perguntas_por_minuto
    )
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
    historico = []
    if body.conversa_id is not None:
        historico = await conversas.ler(state.redis, body.conversa_id, usuario['id'])
    contexto = _contexto(body, carga, historico)
    registro = dict(
        id=uuid4(),
        conversa_id=body.conversa_id or uuid4(),
        usuario_id=usuario['id'],
        pergunta=body.pergunta,
        contexto=body.contexto.model_dump(mode='json'),
        consultas=[],
        nao_sei=False,
    )
    # O agente preenche o andamento enquanto trabalha: numa falha, a auditoria ainda
    # guarda o SQL que já rodou e os tokens já gastos.
    andamento = Andamento()
    inicio = time.monotonic()
    try:
        async with asyncio.timeout(settings.assistente_timeout_s) as limite:
            resposta = await state.assistente.responder(body.pergunta, contexto, andamento)
    except TimeoutError as erro:
        # Só o prazo do assistente vira 503; outro TimeoutError é uma falha inesperada.
        if not limite.expired():
            await _registrar_falha(state, registro, andamento, inicio, _interno(erro))
            raise
        await _registrar_falha(state, registro, andamento, inicio, 'TEMPO_ESGOTADO')
        raise APIError(
            503, 'O assistente demorou demais para responder', 'ASSISTENTE_TEMPO_ESGOTADO'
        ) from None
    except ProvedorIndisponivel as erro:
        await _registrar_falha(state, registro, andamento, inicio, f'PROVEDOR_INDISPONIVEL: {erro}')
        raise APIError(
            503, 'O provedor do modelo está indisponível', 'PROVEDOR_INDISPONIVEL'
        ) from None
    except BancoIndisponivel as erro:
        await _registrar_falha(state, registro, andamento, inicio, f'BANCO_INDISPONIVEL: {erro}')
        raise APIError(
            503, 'O banco de dados do assistente está indisponível', 'BANCO_INDISPONIVEL'
        ) from None
    except Exception as erro:
        await _registrar_falha(state, registro, andamento, inicio, _interno(erro))
        raise
    except asyncio.CancelledError:
        # O cliente fechou o painel no meio da pergunta. CancelledError não é Exception:
        # sem este ramo, as consultas e os tokens já gastos sumiriam da auditoria.
        await asyncio.shield(
            _registrar_falha(state, registro, andamento, inicio, 'CANCELADA_PELO_CLIENTE')
        )
        raise
    finally:
        # A cota conta os tokens de toda pergunta, também os de uma que falhou no meio.
        await limites.gastar_tokens(
            state.redis, usuario['id'], andamento.tokens_entrada + andamento.tokens_saida
        )
    async with state.portal_sessions() as db, db.begin():
        await repository.registrar(db, registro | _da_resposta(resposta))
    await conversas.registrar(
        state.redis,
        registro['conversa_id'],
        usuario['id'],
        body.pergunta,
        resposta,
        contexto.periodo,
    )
    return RespostaPergunta(
        **resposta.model_dump(), id_resposta=registro['id'], conversa_id=registro['conversa_id']
    )


async def conversa(db, conversa_id, usuario) -> Conversa:
    """O histórico permanente, lido da auditoria. Só a dona da conversa vê."""
    linhas = await repository.mensagens(db, conversa_id)
    if not linhas or linhas[0]['usuario_id'] != usuario['id']:
        raise APIError(404, 'Conversa não encontrada', 'CONVERSA_NAO_ENCONTRADA')
    return Conversa(conversa_id=conversa_id, mensagens=[dict(linha) for linha in linhas])


async def auditoria(db, id_resposta, usuario) -> Auditoria:
    linha = await repository.obter(db, id_resposta)
    if linha is None:
        raise APIError(404, 'Resposta não encontrada', 'RESPOSTA_NAO_ENCONTRADA')
    if linha['usuario_id'] != usuario['id'] and usuario['cargo'] != 'diretoria':
        raise APIError(
            403, 'Só o autor da pergunta ou a diretoria veem a auditoria', 'SEM_PERMISSAO'
        )
    return Auditoria(**linha)


def _contexto(body: Pergunta, carga, historico: list[Troca]) -> Contexto:
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
        competencia_inicial=carga['competencia_inicial'],
        data_referencia=carga['data_referencia'],
        tela=pedido.tela and TELAS[pedido.tela],
        periodo=periodo,
        comparacao=comparacao,
        recortes=pedido.recortes,
        historico=historico,
    )


def _das_consultas(consultas: list[Consulta]) -> dict:
    # A última tentativa é a que sustenta a resposta; todas ficam em consultas.
    ultima = consultas[-1] if consultas else None
    return dict(
        consultas=[c.model_dump(mode='json') for c in consultas],
        sql_gerado=ultima and ultima.sql_gerado,
        sql_executado=ultima and ultima.sql_executado,
        # Rejeitada pela guarda ou com erro do banco, a consulta não rodou: não há linhas
        # a contar, e 0 pareceria "rodou e voltou vazia".
        numero_linhas=ultima.total_linhas if ultima and ultima.erro is None else None,
    )


def _da_resposta(resposta: RespostaAgente) -> dict:
    nao_sei = resposta.tipo == 'nao_sei'
    return _das_consultas(resposta.consultas) | dict(
        resposta=resposta.texto,
        nao_sei=nao_sei,
        # O CHECK da auditoria exige motivo no "não sei".
        motivo=resposta.motivo or (resposta.texto if nao_sei else None),
        modelo=resposta.modelo,
        tokens_entrada=resposta.tokens_entrada,
        tokens_saida=resposta.tokens_saida,
        latencia_ms=resposta.latencia_ms,
    )


def _interno(erro: Exception) -> str:
    # Só o tipo: a mensagem de uma exceção inesperada pode trazer dados da consulta.
    return f'ERRO_INTERNO: {type(erro).__name__}'


async def _registrar_falha(state, registro, andamento: Andamento, inicio, erro):
    falha = _das_consultas(andamento.consultas) | dict(
        modelo=andamento.modelo,
        tokens_entrada=andamento.tokens_entrada,
        tokens_saida=andamento.tokens_saida,
        latencia_ms=round((time.monotonic() - inicio) * 1000),
        erro=erro,
    )
    async with state.portal_sessions() as db, db.begin():
        await repository.registrar(db, registro | falha)
