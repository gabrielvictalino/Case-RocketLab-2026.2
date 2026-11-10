"""Insights da Visão Geral e da Receita (seção 6 do system design).

Os fatos saem dos mesmos serviços que a tela usa, numa sessão curta do portal, e o
modelo só redige. O insight fica no Redis por carga, tela, fatos e versão do redator (modelo
e instruções): enquanto os números da tela não mudam, ele não volta ao modelo. Uma inspeção
concluída que muda a taxa de acerto muda os fatos, e o próximo pedido gera outro insight
sem invalidação manual. Uma geração em que poucas observações passam na validação também
fica guardada, por pouco tempo: abrir a tela de novo com os mesmos fatos não volta ao
modelo nem gasta a cota até o prazo vencer.

O módulo não tem `repository`: não há SQL próprio. Os fatos vêm dos serviços de `kpis` e
`receita`, e os recortes válidos, do serviço de `meta`, que confere a carga publicada.
"""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from pydantic import ValidationError
from pydantic_ai import RunUsage
from app.core.limites import FALHAS_DO_REDIS
from venergy_ai.insights import RedatorDeInsights
from venergy_ai.interface import InsightIndisponivel, PedidoInsight, ProvedorIndisponivel, Redator
from venergy_ai.semantica import Periodo as PeriodoDoAgente

from app.core import limites
from app.core.database import sincronizar_com_a_publicacao
from app.core.errors import APIError
from app.core.periodos import Periodo
from app.modules.assistente.service import modelo_configurado
from app.modules.insights import fatos
from app.modules.insights.schemas import TELAS, Insight
from app.modules.kpis import service as kpis
from app.modules.meta import service as meta
from app.modules.receita import service as receita

TTL_S = 24 * 60 * 60
# O modelo não é determinístico: depois deste prazo, os mesmos fatos voltam a ele.
TTL_FALHA_S = 10 * 60
SEM_OBSERVACOES_VALIDAS = 'Nenhuma observação do modelo passou na validação'
# Reserva da cota diária por insight: os fatos e as instruções somam uns 2 mil tokens.
RESERVA_TOKENS = 5_000

logger = logging.getLogger('venergy.insights')


def criar_redator(settings) -> Redator | None:
    modelo = modelo_configurado(settings)
    # O mesmo teto que `_redigir` aplica: o redator o divide entre os modelos da cadeia.
    return None if modelo is None else RedatorDeInsights(modelo, settings.assistente_timeout_s)


async def insight(state, tela, periodo, comparacao, recorte, usuario) -> Insight:
    if state.redator is None:
        raise APIError(503, 'Insights não configurados neste ambiente', 'INSIGHT_INDISPONIVEL')
    # Nenhuma conexão do portal fica presa enquanto o modelo redige.
    async with state.portal_sessions() as db, db.begin():
        await sincronizar_com_a_publicacao(db)
        await _conferir_recorte(db, recorte)
        tela_pronta, lista = await _montar(db, tela, periodo, comparacao, recorte)
    metadados = dict(
        periodo=tela_pronta.periodo, comparacao=tela_pronta.comparacao, carga=tela_pronta.carga
    )
    if not lista:
        raise APIError(503, 'A tela não tem números no período', 'INSIGHT_INDISPONIVEL')
    pedido = PedidoInsight(
        tela=TELAS[tela],
        periodo=_do_agente(tela_pronta.periodo),
        comparacao=tela_pronta.comparacao and _do_agente(tela_pronta.comparacao),
        recortes=recorte.parametros(),
        fatos=lista,
    )
    resumo = hashlib.sha1(pedido.model_dump_json().encode()).hexdigest()
    # Com outro modelo ou outras instruções, o texto guardado não vale mais. A chave usa o
    # UUID da carga, não o batch_id: reimportar o mesmo lote é outra carga, com outra
    # identificação e outra data, e o insight guardado devolveria as da anterior.
    chave = f'insight:{tela_pronta.carga.id}:{tela}:{state.redator.versao}:{resumo}'
    if (guardado := await _ler(state.redis, chave)) is not None:
        return guardado
    falha = f'{chave}:falha'
    if await _falhou_ha_pouco(state.redis, falha):
        raise APIError(503, SEM_OBSERVACOES_VALIDAS, 'INSIGHT_INDISPONIVEL')
    # Só o que vai ao modelo conta no limite e na cota: um insight do cache não gasta.
    settings = state.settings
    reserva = await limites.reservar_cota(
        state.redis, usuario['id'], settings.assistente_cota_tokens_dia, RESERVA_TOKENS
    )
    uso = RunUsage()
    try:
        await limites.consumir(
            state.redis,
            usuario['id'],
            'insights',
            settings.insights_por_minuto,
            rotulo='insights',
            codigo='LIMITE_DE_INSIGHTS',
        )
        gerado = await _redigir(state, pedido, uso)
    except InsightIndisponivel as erro:
        # Só a validação vai para o cache: o tempo esgotado e o provedor fora do ar são
        # passageiros, e o próximo pedido tenta de novo.
        logger.warning('tela=%s %s', tela, erro)
        await _guardar_falha(state.redis, falha)
        raise APIError(503, SEM_OBSERVACOES_VALIDAS, 'INSIGHT_INDISPONIVEL') from None
    finally:
        await limites.acertar_cota(state.redis, reserva, uso.input_tokens + uso.output_tokens)
    if gerado.descartadas:
        logger.info('tela=%s observações descartadas: %s', tela, '; '.join(gerado.descartadas))
    resposta = Insight(
        **metadados,
        tela=tela,
        observacoes=gerado.observacoes,
        modelo=gerado.modelo,
        gerado_em=datetime.now(UTC),
    )
    await _guardar(state.redis, chave, resposta)
    return resposta


async def _redigir(state, pedido: PedidoInsight, uso: RunUsage):
    """Chama o redator com o teto de tempo. Só o que acontece dentro do teto passa pelos
    ramos dele: um TimeoutError de fora (do limite por minuto, por exemplo) não chega a
    ler o `limite`."""
    try:
        async with asyncio.timeout(state.settings.assistente_timeout_s) as limite:
            return await state.redator.redigir(pedido, uso)
    except TimeoutError:
        if not limite.expired():
            raise
        raise APIError(
            503, 'O insight demorou demais para ser gerado', 'INSIGHT_TEMPO_ESGOTADO'
        ) from None
    except ProvedorIndisponivel:
        raise APIError(
            503, 'O provedor do modelo está indisponível', 'PROVEDOR_INDISPONIVEL'
        ) from None


async def _montar(db, tela, periodo, comparacao, recorte):
    """A resposta principal da tela, com os metadados, e os fatos tirados dela."""
    if tela == 'visao-geral':
        cards = await kpis.kpis(db, periodo, comparacao, recorte)
        return cards, fatos.da_visao_geral(cards)
    # Uma consulta e uma decomposição para os três blocos: a chave do cache sai dos fatos,
    # então este custo vale também para um insight que vem do cache.
    ctx, totais = await receita.dados(db, periodo, comparacao, recorte)
    decomposicao = receita.total_decomposicao(ctx, totais)
    # Com um município escolhido, o detalhamento da tela desce para os bairros.
    nivel = 'bairro' if recorte.municipio else 'municipio'
    locais = receita.locais_de(ctx, totais, nivel)
    return decomposicao, fatos.da_receita(decomposicao, receita.grupos_de(ctx, totais), locais)


async def _conferir_recorte(db, recorte):
    """O recorte vem da URL e vai ao prompt: só valem valores que existem na carga.

    Sem recorte (a Visão Geral nunca manda), não há o que conferir nem consulta a fazer.
    Com recorte, as dimensões vêm do serviço de `meta`, que confere antes a carga
    publicada: sem carga, a resposta é 503 `BASE_INDISPONIVEL`, como nas outras rotas."""
    parametros = recorte.parametros()
    if not parametros:
        return
    dimensoes = await meta.filtros(db)
    bairros = dimensoes.bairros
    validos = {
        'municipio': set(dimensoes.municipios),
        'bairro': set(bairros.get(recorte.municipio, ()))
        if recorte.municipio
        else {bairro for lista in bairros.values() for bairro in lista},
        'classe': set(dimensoes.classes),
        'alimentador': set(dimensoes.alimentadores),
    }
    for campo, valor in parametros.items():
        if valor not in validos[campo]:
            raise APIError(422, f'{campo} fora da carga publicada', 'RECORTE_INVALIDO')


def _do_agente(texto: str) -> PeriodoDoAgente:
    periodo = Periodo.parse(texto)
    return PeriodoDoAgente(periodo.inicio, periodo.fim)


async def _ler(redis, chave) -> Insight | None:
    try:
        guardado = await redis.get(chave)
    except FALHAS_DO_REDIS:
        logger.warning('redis indisponível; insight gerado sem cache')
        return None
    if guardado is None:
        return None
    try:
        return Insight.model_validate_json(guardado)
    except ValidationError:
        # Um insight guardado por uma versão anterior do schema é gerado de novo.
        return None


async def _guardar(redis, chave, resposta: Insight):
    try:
        await redis.set(chave, resposta.model_dump_json(), ex=TTL_S)
    except FALHAS_DO_REDIS:
        logger.warning('redis indisponível; insight não guardado')


async def _falhou_ha_pouco(redis, chave) -> bool:
    try:
        return bool(await redis.exists(chave))
    except FALHAS_DO_REDIS:
        # Sem Redis, o pedido vai ao modelo, como no cache do insight.
        return False


async def _guardar_falha(redis, chave):
    try:
        await redis.set(chave, '1', ex=TTL_FALHA_S)
    except FALHAS_DO_REDIS:
        logger.warning('redis indisponível; falha do insight não guardada')
