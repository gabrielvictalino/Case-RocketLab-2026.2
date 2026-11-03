import csv
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pytest

from app.modules.continuidade.service import indicadores

SAMPLES = Path(__file__).resolve().parents[2] / 'contracts/samples'
D = Decimal
INTEGRATION = pytest.mark.integration


def arredondar(value):
    return value.quantize(D('0.01'), rounding=ROUND_HALF_UP)


def ler(nome):
    with (SAMPLES / f'{nome}.csv').open() as file:
        return list(csv.DictReader(file))


async def get(client, headers, rota, **params):
    response = await client.get('/api/v1/continuidade/' + rota, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def test_reagrega_numeradores_e_conta_denominador_uma_vez():
    rows = [
        dict(alimentador='pequeno', chi=D('1.01'), interrupcoes=1, numero_ucs=2),
        dict(alimentador='pequeno', chi=D('2.02'), interrupcoes=2, numero_ucs=2),
        dict(alimentador='grande', chi=D('3.03'), interrupcoes=3, numero_ucs=100),
    ]
    assert indicadores(rows).model_dump() == dict(
        chi=D('6.06'), interrupcoes=6, numero_ucs=102, dec=D('0.06'), fec=D('0.06')
    )
    assert indicadores(rows[:1]).dec == D('0.51')  # meio para cima
    assert all(value is None for value in indicadores([]).model_dump().values())
    zero = indicadores([dict(alimentador='a', chi=D(0), interrupcoes=0, numero_ucs=2)])
    assert zero.dec == zero.fec == 0


@INTEGRATION
async def test_pequeno_lidera_por_dec_e_fec_mas_nao_por_chi(client, headers):
    params = dict(periodo='2025-07..2025-08')
    chi = await get(client, headers, 'ranking', **params)
    assert chi['ordem'] == 'chi'
    assert chi['ranking'][0]['alimentador'] == 'ALM-REC-001'
    assert chi['ranking'][0]['chi'] == '201.00'
    assert chi['ranking'][0]['numero_ucs'] == 60
    assert chi['ranking'][0]['dec'] == '3.35'
    for ordem in ('dec', 'fec'):
        ranking = await get(client, headers, 'ranking', ordem=ordem, **params)
        primeiro = ranking['ranking'][0]
        assert primeiro['alimentador'] == 'ALM-OLI-006'
        assert D(primeiro['dec']) == 8
        assert D(primeiro['fec']) == 2
        assert primeiro['numero_ucs'] == 1
    # Empates seguem o código, independentemente da ordem de leitura no banco.
    empatados = [r['alimentador'] for r in chi['ranking'] if D(r['chi']) == 2]
    assert empatados == sorted(empatados)


@INTEGRATION
@pytest.mark.parametrize('sem_evento', [False, True])
@pytest.mark.parametrize('recorte', [{}, {'municipio': 'Recife'}, {'alimentador': 'ALM-REC-001'}])
async def test_serie_ranking_e_causas_conferidos_contra_csv(client, headers, sem_evento, recorte):
    # Oráculo independente do SQL e da agregação do serviço.
    alimentadores = {r['alimentador']: r for r in ler('dim_alimentador')}
    mensais = [
        r
        for r in ler('continuidade_alimentador_mensal')
        if '2025-07-01' <= r['competencia'] <= '2025-08-01'
        and not (sem_evento and r['flag_evento_atipico'] == 'true')
        and all(alimentadores[r['alimentador']][k] == v for k, v in recorte.items())
    ]
    params = dict(periodo='2025-07..2025-08', sem_evento_atipico=sem_evento, **recorte)
    serie = await get(client, headers, 'serie', **params)
    ranking = await get(client, headers, 'ranking', **params)
    assert serie['carga'] == ranking['carga']
    assert serie['carga']['sintetica'] is True
    assert serie['sem_evento_atipico'] is sem_evento
    assert serie['comparacao'] == ranking['comparacao'] == '2024-07..2024-08'
    assert [p['competencia'] for p in serie['serie']] == ['2025-07-01', '2025-08-01']

    def conferir(indicadores, rows):
        if not rows:
            assert all(
                indicadores[k] is None for k in ('chi', 'interrupcoes', 'numero_ucs', 'dec', 'fec')
            )
            return
        chi = sum(D(r['chi_horas']) for r in rows)
        interrupcoes = sum(int(r['interrupcoes']) for r in rows)
        ucs = sum(int(alimentadores[a]['numero_ucs']) for a in {r['alimentador'] for r in rows})
        assert D(indicadores['chi']) == chi
        assert indicadores['interrupcoes'] == interrupcoes
        assert indicadores['numero_ucs'] == ucs
        assert D(indicadores['dec']) == arredondar(chi / ucs)
        assert D(indicadores['fec']) == arredondar(D(interrupcoes) / ucs)

    conferir(serie['totais'], mensais)
    for ponto in serie['serie']:
        conferir(ponto, [r for r in mensais if r['competencia'] == ponto['competencia']])
    cobertura = {(r['alimentador'], r['competencia'][:7]) for r in mensais}
    ocorrencias = defaultdict(Counter)
    interrupcoes = defaultdict(Counter)
    for row in ler('ocorrencias_uc'):
        if (row['alimentador'], row['data_abertura'][:7]) in cobertura:
            ocorrencias[row['alimentador']][row['causa']] += 1
            interrupcoes[row['alimentador']][row['causa']] += row['flag_sobreposicao'] == 'false'
    assert {r['alimentador'] for r in ranking['ranking']} == {r['alimentador'] for r in mensais}
    for item in ranking['ranking']:
        conferir(item, [r for r in mensais if r['alimentador'] == item['alimentador']])
        assert {r['causa']: r['ocorrencias'] for r in item['causas']} == ocorrencias[
            item['alimentador']
        ]
        assert {r['causa']: r['interrupcoes'] for r in item['causas']} == interrupcoes[
            item['alimentador']
        ]


@INTEGRATION
async def test_exclusao_muda_ranking_totais_e_causas(client, headers):
    params = dict(periodo='2025-07..2025-08')
    com = await get(client, headers, 'ranking', **params)
    sem = await get(client, headers, 'ranking', sem_evento_atipico=True, **params)
    assert com['ranking'][0]['alimentador'] == 'ALM-REC-001'
    assert sem['ranking'][0]['alimentador'] == 'ALM-OLI-006'
    normal = next(r for r in sem['ranking'] if r['alimentador'] == 'ALM-REC-001')
    assert D(normal['chi']) == 1
    assert normal['causas'] == [dict(causa='SINTETICA', ocorrencias=1, interrupcoes=1)]
    serie = await get(client, headers, 'serie', **params)
    filtrada = await get(client, headers, 'serie', sem_evento_atipico=True, **params)
    assert D(serie['totais']['chi']) - D(filtrada['totais']['chi']) == 200
    assert serie['totais']['numero_ucs'] == filtrada['totais']['numero_ucs'] == 300
    assert serie['serie'][1] == filtrada['serie'][1]


@INTEGRATION
async def test_recorte_vazio_e_competencia_totalmente_excluida(client, headers):
    for recorte in (
        {'alimentador': 'ALM-REC-001', 'sem_evento_atipico': True},
        {'municipio': "' OR 1=1 --"},
        {'alimentador': 'inexistente'},
        {'municipio': 'Recife', 'alimentador': 'ALM-OLI-006'},
    ):
        params = dict(periodo='2025-07..2025-07', **recorte)
        serie = await get(client, headers, 'serie', **params)
        assert all(v is None for v in serie['totais'].values())
        assert serie['serie'][0]['dec'] is None
        assert serie['serie'][0]['fec'] is None
        assert (await get(client, headers, 'ranking', **params))['ranking'] == []


@INTEGRATION
async def test_causas_do_detalhe_e_sobreposicoes(client, headers, db):
    # Outra causa não pode desaparecer por não ser a principal mensal.
    # Uma ocorrência sobreposta conta por causa, mas não como interrupção nova.
    async with db.transaction():
        await db.execute("""
            INSERT INTO analytics.ocorrencias_uc
            SELECT 'OC99999999', id_uc, alimentador, data_abertura,
                   data_encerramento, duracao_min, 0, 'OUTRA CAUSA', true
            FROM analytics.ocorrencias_uc
            WHERE alimentador = 'ALM-REC-001' AND data_abertura = '2025-08-02'
        """)
    try:
        data = await get(
            client, headers, 'ranking', periodo='2025-08..2025-08', alimentador='ALM-REC-001'
        )
        item = data['ranking'][0]
        assert item['interrupcoes'] == 1
        assert {c['causa']: c for c in item['causas']} == {
            'SINTETICA': dict(causa='SINTETICA', ocorrencias=1, interrupcoes=1),
            'OUTRA CAUSA': dict(causa='OUTRA CAUSA', ocorrencias=1, interrupcoes=0),
        }
    finally:
        await db.execute("DELETE FROM analytics.ocorrencias_uc WHERE id_ocorrencia='OC99999999'")


@INTEGRATION
async def test_lacuna_na_serie_e_mes_sem_ocorrencia(client, headers, db):
    rows = await db.fetch("""
        SELECT * FROM analytics.continuidade_alimentador_mensal
        WHERE alimentador = 'ALM-OLI-006' AND competencia BETWEEN '2026-05-01' AND '2026-06-01'
    """)
    try:
        await db.execute("""
            DELETE FROM analytics.continuidade_alimentador_mensal
            WHERE alimentador = 'ALM-OLI-006' AND competencia = '2026-05-01'
        """)
        await db.execute("""
            UPDATE analytics.continuidade_alimentador_mensal
            SET chi_horas=0, interrupcoes=0, dec=0, fec=0, causa='SEM OCORRENCIA'
            WHERE alimentador = 'ALM-OLI-006' AND competencia = '2026-06-01'
        """)
        params = dict(periodo='2026-05..2026-06', alimentador='ALM-OLI-006')
        serie = await get(client, headers, 'serie', **params)
        assert serie['serie'][0]['dec'] is None
        assert D(serie['serie'][1]['dec']) == 0
        assert D(serie['serie'][1]['fec']) == 0
        assert serie['totais']['numero_ucs'] == 1
    finally:
        await db.execute("""
            DELETE FROM analytics.continuidade_alimentador_mensal
            WHERE alimentador = 'ALM-OLI-006'
              AND competencia BETWEEN '2026-05-01' AND '2026-06-01'
        """)
        await db.copy_records_to_table(
            'continuidade_alimentador_mensal',
            schema_name='analytics',
            records=[tuple(r) for r in rows],
        )


@INTEGRATION
@pytest.mark.parametrize('rota', ['serie', 'ranking'])
async def test_autenticacao_e_validacao(client, headers, rota):
    url = '/api/v1/continuidade/' + rota
    assert (await client.get(url, params={'periodo': '2025-01..2025-02'})).status_code == 401
    for params in (
        {},
        {'periodo': '2025-13..2025-14'},
        {'periodo': '2025-02..2025-01'},
        {'periodo': '2022-06..2022-07'},
        {'periodo': '2025-01..2025-02', 'comparacao': '2022-01..2022-02'},
        {'periodo': '2025-01..2025-02', 'sem_evento_atipico': 'invalido'},
    ):
        response = await client.get(url, headers=headers, params=params)
        assert response.status_code == 422, response.text
    if rota == 'ranking':
        response = await client.get(
            url, headers=headers, params=dict(periodo='2025-01..2025-02', ordem='chi; DROP TABLE')
        )
        assert response.status_code == 422


@INTEGRATION
async def test_primeiro_mes_sem_comparacao_e_virada_de_ano(client, headers):
    primeiro = await get(client, headers, 'serie', periodo='2022-07..2022-07')
    assert primeiro['comparacao'] is None
    data = await get(client, headers, 'serie', periodo='2024-12..2025-01')
    assert [p['competencia'] for p in data['serie']] == ['2024-12-01', '2025-01-01']
