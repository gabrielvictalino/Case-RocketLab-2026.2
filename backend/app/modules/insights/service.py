"""Insights da Visão Geral e da Receita (seção 6 do system design).

Os fatos saem dos mesmos serviços que a tela usa, numa sessão curta do portal, e o
modelo só redige. O insight fica no Redis por tela, fatos e versão do redator (modelo e
instruções): enquanto os números da tela não mudam, ele não volta ao modelo. Uma inspeção
concluída que muda a taxa de acerto muda os fatos, e o próximo pedido gera outro insight
sem invalidação manual.

O módulo não tem `repository`: não há SQL próprio. Os fatos vêm dos serviços de `kpis` e
`receita`, e os recortes válidos, das dimensões de `meta`.
"""

import asyncio
import hashlib
import logging
from datetime import UTC, datetime

from pydantic import ValidationError
from pydantic_ai import RunUsage
from redis.exceptions import RedisError
from venergy_ai.insights import RedatorDeInsights
from venergy_ai.interface import InsightIndisponivel, PedidoInsight, ProvedorIndisponivel, Redator
from venergy_ai.semantica import Periodo as PeriodoDoAgente

from app.core import limites
from app.core.errors import APIError
from app.core.periodos import Periodo
from app.modules.assistente.service import modelo_configurado
from app.modules.insights import fatos
from app.modules.insights.schemas import TELAS, Insight
from app.modules.kpis import service as kpis
from app.modules.meta import repository as meta
from app.modules.receita import service as receita

TTL_S = 24 * 60 * 60
# Reserva da cota diária por insight: os fatos e as instruções somam uns 2 mil tokens.
RESERVA_TOKENS = 5_000

logger = logging.getLogger('venergy.insights')


def criar_redator(settings) -> Redator | None:
    modelo = modelo_configurado(settings)
    return None if modelo is None else RedatorDeInsights(modelo)


async def insight(state, tela, periodo, comparacao, recorte, usuario) -> Insight:
    if state.redator is None:
        raise APIError(503, 'Insights não configurados neste ambiente', 'INSIGHT_INDISPONIVEL')
    # Nenhuma conexão do portal fica presa enquanto o modelo redige.
    async with state.portal_sessions() as db, db.begin():
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
    # Com outro modelo ou outras instruções, o texto guardado não vale mais.
    chave = f'insight:{tela_pronta.carga.batch_id}:{tela}:{state.redator.versao}:{resumo}'
    if (guardado := await _ler(state.redis, chave)) is not None:
        return guardado
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
        gerado = await _redigir(state, pedido, uso, tela)
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


async def _redigir(state, pedido: PedidoInsight, uso: RunUsage, tela: str):
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
    except InsightIndisponivel as erro:
        logger.warning('tela=%s %s', tela, erro)
        raise APIError(
            503, 'Nenhuma observação do modelo passou na validação', 'INSIGHT_INDISPONIVEL'
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
    """O recorte vem da URL e vai ao prompt: só valem valores que existem na carga."""
    dimensoes = await meta.dimensoes(db)
    bairros = dimensoes['bairros']
    validos = {
        'municipio': set(dimensoes['municipios']),
        'bairro': set(bairros.get(recorte.municipio, ()))
        if recorte.municipio
        else {bairro for lista in bairros.values() for bairro in lista},
        'classe': set(dimensoes['classes']),
        'alimentador': set(dimensoes['alimentadores']),
    }
    for campo, valor in recorte.parametros().items():
        if valor not in validos[campo]:
            raise APIError(422, f'{campo} fora da carga publicada', 'RECORTE_INVALIDO')


def _do_agente(texto: str) -> PeriodoDoAgente:
    periodo = Periodo.parse(texto)
    return PeriodoDoAgente(periodo.inicio, periodo.fim)


async def _ler(redis, chave) -> Insight | None:
    try:
        guardado = await redis.get(chave)
    except RedisError:
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
    except RedisError:
        logger.warning('redis indisponível; insight não guardado')
