import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.periodos import Periodo
from app.modules.kpis import repository as kpis_repository
from app.modules.kpis.service import indicador
from app.modules.metricas import Recorte, razao
from app.modules.receita import repository as receita_repository

SAMPLES = Path(__file__).resolve().parents[2] / 'contracts/samples'
D = Decimal
INTEGRATION = pytest.mark.integration


def arredondar(value, casas='0.01'):
    return value.quantize(D(casas), rounding=ROUND_HALF_UP)


def test_variacoes_e_denominadores_nulos():
    assert indicador(D(120), D(100)).model_dump() == dict(
        valor=D(120), comparacao=D(100), variacao=D(20), variacao_pct=D(20)
    )
    assert indicador(D(0), D(10)).variacao_pct == D(-100)
    assert indicador(D(10), D(0)).variacao == D(10)
    assert indicador(D(10), D(0)).variacao_pct is None
    assert indicador(None, D(10)).variacao is None
    assert indicador(D(10), None).variacao is None
    assert razao(0, 10, 100) == D(0)
    assert razao(10, 0) is None
    assert razao(None, 10) is None


async def get(client, headers, path='/kpis', **params):
    response = await client.get('/api/v1' + path, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def agregado(inicio, fim, **recorte):
    with (SAMPLES / 'receita_volume_mensal.csv').open() as file:
        rows = [
            r
            for r in csv.DictReader(file)
            if inicio <= r['competencia'] <= fim and all(r[k] == v for k, v in recorte.items())
        ]
    return {
        key: sum((D(r[key]) for r in rows), D(0))
        for key in (
            'receita',
            'receita_arrecadada',
            'volume_faturado_kwh',
            'componente_tarifa_reais',
            'componente_bandeira_reais',
        )
    }


def detalhe(inicio, fim, **recorte):
    with (SAMPLES / 'dim_uc.csv').open() as file:
        ids = {
            r['id_uc'] for r in csv.DictReader(file) if all(r[k] == v for k, v in recorte.items())
        }
    with (SAMPLES / 'uc_consumo_faturamento_mensal.csv').open() as file:
        rows = [
            r
            for r in csv.DictReader(file)
            if inicio <= r['competencia'] <= fim and r['id_uc'] in ids
        ]
    return dict(
        receita=sum((D(r['valor_total']) for r in rows), D(0)),
        receita_arrecadada=sum((D(r['valor_arrecadado']) for r in rows), D(0)),
        volume_faturado_kwh=sum((D(r['volume_faturado_kwh']) for r in rows), D(0)),
        componente_tarifa_reais=arredondar(
            sum((D(r['volume_faturado_kwh']) * D(r['tarifa_base'] or 0) for r in rows), D(0))
        ),
        componente_bandeira_reais=arredondar(
            sum((D(r['volume_faturado_kwh']) * D(r['adicional_bandeira'] or 0) for r in rows), D(0))
        ),
    )


@pytest.fixture
async def sessao_metricas(infrastructure):
    engine = create_async_engine(infrastructure['settings'].database_url_portal)
    try:
        async with async_sessionmaker(engine)() as session:
            yield session
    finally:
        await engine.dispose()


@INTEGRATION
async def test_oito_cards_e_formulas_da_amostra(client, headers):
    data = await get(client, headers, periodo='2025-07..2026-06')
    assert data['comparacao'] == '2024-07..2025-06'
    assert data['carga']['sintetica'] is True
    assert len(set(data) - {'periodo', 'comparacao', 'carga', 'sem_evento_atipico'}) == 8
    atual = agregado('2025-07-01', '2026-06-01')
    anterior = agregado('2024-07-01', '2025-06-01')
    for key in ('receita', 'receita_arrecadada', 'volume_faturado_kwh'):
        assert D(data[key]['valor']) == atual[key]
        assert D(data[key]['comparacao']) == anterior[key]
        assert D(data[key]['variacao']) == atual[key] - anterior[key]
        assert D(data[key]['variacao_pct']) == arredondar(
            (atual[key] - anterior[key]) / anterior[key] * 100
        )
    assert D(data['tarifa_media']['valor']) == arredondar(
        atual['receita'] / atual['volume_faturado_kwh'], '0.000001'
    )
    assert D(data['inadimplencia']['valor']) == arredondar(
        (atual['receita'] - atual['receita_arrecadada']) / atual['receita'] * 100
    )
    assert D(data['ucs']['ativas']['valor']) == 300
    assert D(data['ucs']['com_gd']['valor']) == 1


@INTEGRATION
@pytest.mark.parametrize(
    'recorte',
    [
        {},
        {'municipio': 'Recife'},
        {'municipio': 'Recife', 'bairro': 'Bairro sintético 1', 'classe': 'Residencial'},
        {'alimentador': 'ALM-REC-001'},
        {'municipio': 'inexistente'},
    ],
)
async def test_cruzado_com_serie(client, headers, recorte):
    params = dict(periodo='2025-07..2026-06', comparacao='2023-07..2024-06', **recorte)
    kpis = await get(client, headers, **params)
    serie = await get(client, headers, '/kpis/serie', **params)
    assert kpis['carga']['id'] == serie['carga']['id']
    for key in ('receita', 'volume_faturado_kwh'):
        valores = [D(p[key]) for p in serie['serie'] if p[key] is not None]
        total = sum(valores) if valores else None
        assert total == (D(kpis[key]['valor']) if kpis[key]['valor'] is not None else None)
    assert len(serie['serie']) == 12
    assert [p['competencia'] for p in serie['serie']] == sorted(
        p['competencia'] for p in serie['serie']
    )


@INTEGRATION
@pytest.mark.parametrize(
    'recorte',
    [
        {'municipio': 'Recife'},
        {'alimentador': 'ALM-REC-001'},
        {'alimentador': 'ALM-REC-001', 'bairro': 'Bairro sintético 1', 'classe': 'Residencial'},
    ],
)
async def test_recortes_conferidos_contra_csv(client, headers, sessao_metricas, recorte):
    # O oráculo lê o CSV diretamente, sem usar o SQL compartilhado pelas rotas.
    amostra = detalhe if 'alimentador' in recorte else agregado
    params = dict(periodo='2025-07..2026-06', comparacao='2023-07..2024-06', **recorte)
    kpis = await get(client, headers, **params)
    for campo, inicio, fim in (
        ('valor', '2025-07-01', '2026-06-01'),
        ('comparacao', '2023-07-01', '2024-06-01'),
    ):
        esperado = amostra(inicio, fim, **recorte)
        periodo = Periodo(date.fromisoformat(inicio), date.fromisoformat(fim))
        totais = await receita_repository.totais(sessao_metricas, periodo, Recorte(**recorte))
        assert dict(totais) == esperado
        for key in ('receita', 'receita_arrecadada', 'volume_faturado_kwh'):
            assert D(kpis[key][campo]) == esperado[key]
        assert D(kpis['tarifa_media'][campo]) == arredondar(
            esperado['receita'] / esperado['volume_faturado_kwh'], '0.000001'
        )
        assert D(kpis['inadimplencia'][campo]) == arredondar(
            (esperado['receita'] - esperado['receita_arrecadada']) / esperado['receita'] * 100
        )
        serie = await get(
            client, headers, '/kpis/serie', periodo=f'{inicio[:7]}..{fim[:7]}', **recorte
        )
        for ponto in serie['serie']:
            mensal = amostra(ponto['competencia'], ponto['competencia'], **recorte)
            for key in ('receita', 'volume_faturado_kwh'):
                assert D(ponto[key]) == mensal[key]


@INTEGRATION
async def test_dec_fec_ponderados_com_denominador_fixo(client, headers):
    # 5 alimentadores têm CHI=1 e um tem CHI=4 por mês, para 300 UCs.
    # Uma média simples dos DEC/FEC ou um denominador somado por mês falharia.
    data = await get(client, headers, periodo='2024-01..2024-02')
    assert D(data['continuidade']['dec']['valor']) == D('0.06')  # 18 / 300
    assert D(data['continuidade']['fec']['valor']) == D('0.04')  # 12 / 300
    pequeno = await get(client, headers, periodo='2024-01..2024-02', alimentador='ALM-OLI-006')
    assert D(pequeno['continuidade']['dec']['valor']) == 8
    assert D(pequeno['continuidade']['fec']['valor']) == 2
    atipico = await get(client, headers, periodo='2025-07..2025-07')
    with (SAMPLES / 'continuidade_alimentador_mensal.csv').open() as file:
        rows = [r for r in csv.DictReader(file) if r['competencia'] == '2025-07-01']
    assert D(atipico['continuidade']['dec']['valor']) == arredondar(
        sum(D(r['chi_horas']) for r in rows) / 300
    )


@INTEGRATION
async def test_recorte_continuidade_nao_inclui_outras_ucs(client, headers, db):
    data = await get(
        client, headers, periodo='2025-07..2025-07', municipio='Recife', classe='Residencial'
    )
    expected = await db.fetchrow("""
        SELECT sum(o.duracao_efetiva_min) / 60 / count(DISTINCT u.id_uc) AS dec,
               count(o.id_ocorrencia) FILTER (WHERE NOT o.flag_sobreposicao)::numeric
                   / count(DISTINCT u.id_uc) AS fec
        FROM analytics.dim_uc u
        LEFT JOIN analytics.ocorrencias_uc o ON o.id_uc = u.id_uc
            AND o.data_abertura >= '2025-07-01' AND o.data_abertura < '2025-08-01'
        WHERE u.municipio = 'Recife' AND u.classe = 'Residencial'
    """)
    assert D(data['continuidade']['dec']['valor']) == arredondar(expected['dec'] or D(0))
    assert D(data['continuidade']['fec']['valor']) == arredondar(expected['fec'])


@INTEGRATION
async def test_gd_temporal_e_ucs_distintas(client, headers):
    antes = await get(client, headers, periodo='2024-01..2024-12')
    depois = await get(client, headers, periodo='2025-01..2025-12')
    assert D(antes['ucs']['com_gd']['valor']) == 0
    assert D(depois['ucs']['com_gd']['valor']) == 1
    assert D(antes['ucs']['ativas']['valor']) == 299
    assert D(depois['ucs']['ativas']['valor']) == 300


@INTEGRATION
@pytest.mark.parametrize('fuso', ['UTC', 'America/Fortaleza', 'Pacific/Kiritimati'])
async def test_gd_limite_da_competencia_independe_do_fuso(sessao_metricas, fuso):
    await sessao_metricas.execute(
        text("SELECT set_config('TimeZone', :fuso, true)"), {'fuso': fuso}
    )
    for mes, esperado in ((date(2024, 12, 1), 0), (date(2025, 1, 1), 1)):
        ucs = await kpis_repository.ucs(sessao_metricas, Periodo(mes, mes), Recorte())
        assert ucs['com_gd'] == esperado


@INTEGRATION
async def test_acerto_historico_nulo_zero_e_nova_inspecao(client, headers):
    historico = await get(client, headers, periodo='2025-08..2025-12')
    with (SAMPLES / 'inspecoes_historicas.csv').open() as file:
        rows = list(csv.DictReader(file))
    confirmadas = sum(r['resultado'] == 'IRREGULARIDADE CONFIRMADA' for r in rows)
    assert D(historico['taxa_acerto']['valor']) == arredondar(D(confirmadas) / len(rows) * 100)
    assert historico['taxa_acerto']['comparacao'] is None
    assert historico['taxa_acerto']['variacao'] is None
    params = dict(periodo='2026-06..2026-06')
    assert (await get(client, headers, **params))['taxa_acerto']['valor'] is None
    result = await client.post(
        '/api/v1/ordens-inspecao', headers=headers, json={'ucs': ['UC100001']}
    )
    assert result.status_code == 201, result.text
    ordem = '/api/v1/ordens-inspecao/' + result.json()['criadas'][0]['id']
    result = await client.post(ordem + '/despachar', headers=headers, json={'inspetor': 'INSP-001'})
    assert result.status_code == 200
    result = await client.post(
        ordem + '/resultado',
        headers=headers,
        json={'resultado': 'SEM IRREGULARIDADE', 'kwh_recuperado': 0, 'data': '2026-06-30'},
    )
    assert result.status_code == 200, result.text
    assert D((await get(client, headers, **params))['taxa_acerto']['valor']) == 0
    assert (await get(client, headers, **params, municipio='Olinda'))['taxa_acerto'][
        'valor'
    ] is None


@INTEGRATION
async def test_comparacao_padrao_indisponivel(client, headers):
    data = await get(client, headers, periodo='2022-07..2022-07')
    assert data['comparacao'] is None
    assert data['receita']['valor'] is not None
    assert data['receita']['comparacao'] is None
    assert data['receita']['variacao'] is None
    assert data['receita']['variacao_pct'] is None


@INTEGRATION
async def test_recorte_vazio_nao_vira_zero(client, headers):
    data = await get(client, headers, periodo='2025-08..2025-12', municipio="' OR 1=1 --")
    for key in ('receita', 'tarifa_media', 'inadimplencia', 'taxa_acerto'):
        assert all(v is None for v in data[key].values())
    assert data['ucs']['ativas']['valor'] is None
    assert data['continuidade']['dec']['valor'] is None


@INTEGRATION
async def test_lacuna_na_serie_e_dado_zero(client, headers, db):
    # Não confundir uma competência ausente com uma linha de faturamento zerada.
    rows = await db.fetch("""
        SELECT * FROM analytics.receita_volume_mensal
        WHERE competencia BETWEEN '2026-05-01' AND '2026-06-01'
    """)
    try:
        await db.execute("""
            DELETE FROM analytics.receita_volume_mensal WHERE competencia = '2026-05-01'
        """)
        await db.execute("""
            UPDATE analytics.receita_volume_mensal
            SET receita = 0, receita_arrecadada = 0, volume_faturado_kwh = 0
            WHERE competencia = '2026-06-01'
        """)
        data = await get(client, headers, '/kpis/serie', periodo='2026-05..2026-06')
        assert data['serie'][0] == dict(
            competencia='2026-05-01', receita=None, volume_faturado_kwh=None
        )
        assert D(data['serie'][1]['receita']) == 0
        cards = await get(client, headers, periodo='2026-06..2026-06')
        assert D(cards['receita']['valor']) == 0
        assert cards['tarifa_media']['valor'] is None
        assert cards['inadimplencia']['valor'] is None
    finally:
        await db.execute("""
            DELETE FROM analytics.receita_volume_mensal
            WHERE competencia BETWEEN '2026-05-01' AND '2026-06-01'
        """)
        await db.copy_records_to_table(
            'receita_volume_mensal', schema_name='analytics', records=[tuple(r) for r in rows]
        )


@INTEGRATION
async def test_continuidade_sem_cobertura_vem_nula(client, headers, db):
    rows = await db.fetch("""
        DELETE FROM analytics.continuidade_alimentador_mensal
        WHERE competencia = '2026-06-01' RETURNING *
    """)
    try:
        for recorte in ({}, {'classe': 'Residencial'}):
            data = await get(client, headers, periodo='2026-06..2026-06', **recorte)
            assert data['continuidade']['dec']['valor'] is None
            assert data['continuidade']['fec']['valor'] is None
            assert data['receita']['valor'] is not None
    finally:
        await db.copy_records_to_table(
            'continuidade_alimentador_mensal',
            schema_name='analytics',
            records=[tuple(r) for r in rows],
        )


@INTEGRATION
@pytest.mark.parametrize('path', ['/kpis', '/kpis/serie'])
async def test_autenticacao_e_validacao(client, headers, path):
    url = '/api/v1' + path
    assert (await client.get(url, params={'periodo': '2025-01..2025-02'})).status_code == 401
    for params in (
        {},
        {'periodo': '2025-13..2025-14'},
        {'periodo': '2025-02..2025-01'},
        {'periodo': '2022-06..2022-07'},
        {'periodo': '2025-01..2025-02', 'comparacao': '2022-01..2022-02'},
    ):
        response = await client.get(url, headers=headers, params=params)
        assert response.status_code == 422, response.text
        assert response.json()['code'] in (
            'VALIDACAO_INVALIDA',
            'PERIODO_INVALIDO',
            'PERIODO_FORA_DA_BASE',
        )
