import asyncio
import inspect
import json
from decimal import Decimal

import pytest
from pydantic_ai import ModelHTTPError, ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from redis.asyncio import Redis
from venergy_ai.insights import RedatorDeInsights

pytestmark = pytest.mark.integration

PERIODO = dict(periodo='2025-07..2026-06')


def br(valor, casas=2):
    """O número como o redator escreveria: 1.234.567,89."""
    texto = f'{Decimal(valor):,.{casas}f}'
    return texto.replace(',', '_').replace('.', ',').replace('_', '.')


def usar_modelo(app, escrever):
    """O modelo simulado lê os fatos do pedido e devolve as observações de `escrever`."""
    chamadas = []

    async def responder(mensagens, info):
        chamadas.append(info)
        if isinstance(escrever, Exception):
            raise escrever
        pedido = mensagens[-1].parts[-1].content
        bloco = json.loads(pedido.split('<fatos>', 1)[1].rsplit('</fatos>', 1)[0])
        fatos = {fato['chave']: fato for fato in bloco['fatos']}
        chamadas[-1] = (info, fatos)
        observacoes = escrever(fatos)
        if inspect.isawaitable(observacoes):
            observacoes = await observacoes
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {'observacoes': observacoes})]
        )

    app.state.redator = RedatorDeInsights(FunctionModel(responder, model_name='simulado'))
    return chamadas


def da_receita_total(fatos):
    receita = br(fatos['receita']['valor'])
    return [{'chave': 'receita', 'texto': f'A receita faturada foi de R$ {receita}.'}]


def da_visao_geral(fatos):
    ucs = br(fatos['ucs_ativas']['valor'], 0)
    return [
        *da_receita_total(fatos),
        {'chave': 'receita', 'texto': 'A receita faturada cresceu 987,65% no período.'},
        {'chave': 'ucs_ativas', 'texto': f'São {ucs} UCs ativas.'},
    ]


@pytest.fixture
async def portal_insights(portal):
    """O app sem os insights e os limites que outros testes deixaram no Redis."""
    app, http = portal
    for padrao in ('insight:*', 'rl:*'):
        async for chave in app.state.redis.scan_iter(padrao):
            await app.state.redis.delete(chave)
    resposta = await http.post(
        '/api/v1/auth/login', json={'login': 'perdas', 'senha': 'Demo-Venergy-2026!'}
    )
    headers = {'Authorization': 'Bearer ' + resposta.json()['access_token']}
    return app, http, headers


async def test_insight_da_visao_geral(portal_insights):
    app, http, headers = portal_insights
    chamadas = usar_modelo(app, da_visao_geral)
    resposta = await http.get('/api/v1/insights/visao-geral', params=PERIODO, headers=headers)
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo['tela'] == 'visao-geral' and corpo['modelo'] == 'simulado'
    assert corpo['periodo'] == '2025-07..2026-06' and corpo['comparacao'] == '2024-07..2025-06'
    assert corpo['carga']['batch_id'] and corpo['gerado_em']
    # A observação com o número inventado foi descartada.
    assert [o['chave'] for o in corpo['observacoes']] == ['receita', 'ucs_ativas']
    receita = corpo['observacoes'][0]
    assert receita['metrica'] == 'Receita faturada'
    [citado] = receita['valores']
    assert (citado['campo'], citado['unidade']) == ('valor', 'R$')
    cards = (await http.get('/api/v1/kpis', params=PERIODO, headers=headers)).json()
    assert Decimal(citado['valor']) == Decimal(cards['receita']['valor'])
    assert citado['trecho'] in receita['texto']
    # Os fatos são os cards da tela, com as etiquetas dela.
    _, fatos = chamadas[0]
    assert {'receita', 'inadimplencia', 'dec', 'fec', 'taxa_acerto'} <= set(fatos)
    assert fatos['inadimplencia']['metrica'] == 'Inadimplência'
    assert Decimal(fatos['dec']['valor']) == Decimal(cards['continuidade']['dec']['valor'])


async def test_insight_da_receita(portal_insights):
    app, http, headers = portal_insights

    def escrever(fatos):
        bandeira = br(abs(Decimal(fatos['efeito_bandeira']['valor'])))
        return [{'chave': 'efeito_bandeira', 'texto': f'O efeito bandeira somou R$ {bandeira}.'}]

    chamadas = usar_modelo(app, escrever)
    resposta = await http.get('/api/v1/insights/receita', params=PERIODO, headers=headers)
    assert resposta.status_code == 200, resposta.text
    [observacao] = resposta.json()['observacoes']
    assert observacao['metrica'] == 'Efeito bandeira'
    _, fatos = chamadas[0]
    cascata = (
        await http.get('/api/v1/receita/decomposicao', params=PERIODO, headers=headers)
    ).json()
    assert Decimal(fatos['efeito_bandeira']['valor']) == Decimal(cascata['efeitos']['bandeira'])
    assert Decimal(fatos['receita']['variacao']) == Decimal(cascata['variacao'])
    assert {'efeito_volume', 'efeito_reajuste', 'efeito_mix', 'volume_faturado'} <= set(fatos)
    assert fatos['grupo_gd']['metrica'] == 'Volume das UCs com GD'
    # Na amostra há três municípios: as pontas do detalhamento são os três, uma vez cada.
    assert sorted(k for k in fatos if k.startswith('local:')) == [
        'local:Jaboatão',
        'local:Olinda',
        'local:Recife',
    ]


async def test_receita_de_um_municipio_desce_para_os_bairros(portal_insights):
    app, http, headers = portal_insights
    chamadas = usar_modelo(app, da_receita_total)
    resposta = await http.get(
        '/api/v1/insights/receita', params=PERIODO | {'municipio': 'Recife'}, headers=headers
    )
    assert resposta.status_code == 200, resposta.text
    _, fatos = chamadas[0]
    locais = [k for k in fatos if k.startswith('local:')]
    assert locais and all(k.endswith('(Recife)') for k in locais)
    assert len(locais) <= 6


async def test_insight_vem_do_cache_enquanto_os_fatos_nao_mudam(portal_insights):
    app, http, headers = portal_insights
    chamadas = usar_modelo(app, da_visao_geral)
    url = '/api/v1/insights/visao-geral'
    primeira = (await http.get(url, params=PERIODO, headers=headers)).json()
    segunda = (await http.get(url, params=PERIODO, headers=headers)).json()
    assert len(chamadas) == 1
    assert segunda == primeira
    # Outro recorte muda os fatos: o insight é gerado de novo.
    resposta = await http.get(url, params=PERIODO | {'classe': 'Residencial'}, headers=headers)
    assert resposta.status_code == 200, resposta.text
    assert len(chamadas) == 2


async def test_limite_conta_so_o_que_vai_ao_modelo(portal_insights):
    app, http, headers = portal_insights
    app.state.settings = app.state.settings.model_copy(update={'insights_por_minuto': 1})
    usar_modelo(app, da_visao_geral)
    url = '/api/v1/insights/visao-geral'
    assert (await http.get(url, params=PERIODO, headers=headers)).status_code == 200
    # Do cache: não gasta o limite.
    assert (await http.get(url, params=PERIODO, headers=headers)).status_code == 200
    resposta = await http.get(url, params=PERIODO | {'classe': 'Rural'}, headers=headers)
    assert resposta.status_code == 429
    assert resposta.json()['code'] == 'LIMITE_DE_PERGUNTAS'
    assert int(resposta.headers['Retry-After']) >= 1


async def test_sem_observacao_valida_responde_503(portal_insights):
    app, http, headers = portal_insights
    usar_modelo(app, lambda fatos: [{'chave': 'receita', 'texto': 'A receita subiu 987,65%.'}])
    resposta = await http.get('/api/v1/insights/visao-geral', params=PERIODO, headers=headers)
    assert resposta.status_code == 503
    assert resposta.json()['code'] == 'INSIGHT_INDISPONIVEL'
    # Nada vai para o cache: o próximo pedido tenta de novo.
    assert [chave async for chave in app.state.redis.scan_iter('insight:*')] == []


async def test_provedor_fora_do_ar_responde_503(portal_insights):
    app, http, headers = portal_insights
    usar_modelo(app, ModelHTTPError(503, 'simulado', 'fora do ar'))
    resposta = await http.get('/api/v1/insights/visao-geral', params=PERIODO, headers=headers)
    assert resposta.status_code == 503
    assert resposta.json()['code'] == 'PROVEDOR_INDISPONIVEL'


async def test_modelo_lento_responde_503(portal_insights):
    app, http, headers = portal_insights
    app.state.settings = app.state.settings.model_copy(update={'assistente_timeout_s': 0.2})

    async def devagar(fatos):
        await asyncio.sleep(2)
        return da_visao_geral(fatos)

    usar_modelo(app, devagar)
    resposta = await http.get('/api/v1/insights/visao-geral', params=PERIODO, headers=headers)
    assert resposta.status_code == 503
    assert resposta.json()['code'] == 'INSIGHT_TEMPO_ESGOTADO'


async def test_sem_chave_do_modelo_responde_503(portal_insights):
    app, http, headers = portal_insights
    assert app.state.redator is None
    resposta = await http.get('/api/v1/insights/visao-geral', params=PERIODO, headers=headers)
    assert resposta.status_code == 503
    assert resposta.json()['code'] == 'INSIGHT_INDISPONIVEL'


async def test_redis_fora_do_ar_gera_sem_cache(portal_insights):
    app, http, headers = portal_insights
    chamadas = usar_modelo(app, da_visao_geral)
    original = app.state.redis
    app.state.redis = Redis.from_url('redis://127.0.0.1:1/0', socket_connect_timeout=0.2)
    try:
        url = '/api/v1/insights/visao-geral'
        assert (await http.get(url, params=PERIODO, headers=headers)).status_code == 200
        assert (await http.get(url, params=PERIODO, headers=headers)).status_code == 200
    finally:
        await app.state.redis.aclose()
        app.state.redis = original
    assert len(chamadas) == 2


async def test_parametros_validados_como_na_tela(portal_insights):
    app, http, headers = portal_insights
    usar_modelo(app, da_visao_geral)
    receita = await http.get(
        '/api/v1/insights/receita',
        params=PERIODO | {'alimentador': 'ALM-REC-001'},
        headers=headers,
    )
    assert receita.status_code == 422 and receita.json()['code'] == 'RECORTE_INVALIDO'
    periodo = await http.get(
        '/api/v1/insights/visao-geral', params={'periodo': '2030-01..2030-12'}, headers=headers
    )
    assert periodo.status_code == 422 and periodo.json()['code'] == 'PERIODO_FORA_DA_BASE'
    assert (
        await http.get('/api/v1/insights/perdas', params=PERIODO, headers=headers)
    ).status_code == 422
    assert (await http.get('/api/v1/insights/visao-geral', params=PERIODO)).status_code == 401
