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


def test_indicadores_arredondam_e_distingem_ausencia_de_zero():
    assert indicadores(dict(chi=D('1.01'), interrupcoes=1, numero_ucs=2)).model_dump() == dict(
        chi=D('1.01'), interrupcoes=1, numero_ucs=2, dec=D('0.51'), fec=D('0.50')
    )
    ausente = indicadores(dict(chi=None, interrupcoes=None, numero_ucs=None))
    assert all(value is None for value in ausente.model_dump().values())
    zero = indicadores(dict(chi=D(0), interrupcoes=0, numero_ucs=2))
    assert zero.dec == zero.fec == 0
    sem_ucs = indicadores(dict(chi=D(1), interrupcoes=1, numero_ucs=0))
    assert sem_ucs.dec is sem_ucs.fec is None


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
@pytest.mark.parametrize('fim', ['2025-07', '2025-08'])
async def test_serie_ranking_e_causas_conferidos_contra_csv(
    client, headers, sem_evento, recorte, fim
):
    # Oráculo independente do SQL e da agregação do serviço.
    alimentadores = {r['alimentador']: r for r in ler('dim_alimentador')}
    mensais = [
        r
        for r in ler('continuidade_alimentador_mensal')
        if '2025-07-01' <= r['competencia'] <= fim + '-01'
        and all(alimentadores[r['alimentador']][k] == v for k, v in recorte.items())
    ]
    params = dict(periodo=f'2025-07..{fim}', sem_evento_atipico=sem_evento, **recorte)
    serie = await get(client, headers, 'serie', **params)
    ranking = await get(client, headers, 'ranking', **params)
    assert serie['carga'] == ranking['carga']
    assert serie['carga']['sintetica'] is True
    assert serie['sem_evento_atipico'] is sem_evento
    assert serie['comparacao'] == ranking['comparacao'] == f'2024-07..{fim.replace("2025", "2024")}'
    assert [p['competencia'] for p in serie['serie']] == [
        mes for mes in ['2025-07-01', '2025-08-01'] if mes <= fim + '-01'
    ]

    def conferir(indicadores, rows):
        validas = [r for r in rows if not (sem_evento and r['flag_evento_atipico'] == 'true')]
        if not validas:
            assert all(
                indicadores[k] is None for k in ('chi', 'interrupcoes', 'numero_ucs', 'dec', 'fec')
            )
            return
        chi = sum(D(r['chi_horas']) for r in validas)
        interrupcoes = sum(int(r['interrupcoes']) for r in validas)
        ucs = sum(int(alimentadores[a]['numero_ucs']) for a in {r['alimentador'] for r in validas})
        assert D(indicadores['chi']) == chi
        assert indicadores['interrupcoes'] == interrupcoes
        assert indicadores['numero_ucs'] == ucs
        assert D(indicadores['dec']) == arredondar(chi / ucs)
        assert D(indicadores['fec']) == arredondar(D(interrupcoes) / ucs)

    conferir(serie['totais'], mensais)
    for ponto in serie['serie']:
        conferir(ponto, [r for r in mensais if r['competencia'] == ponto['competencia']])
    cobertura = {
        (r['alimentador'], r['competencia'][:7])
        for r in mensais
        if not (sem_evento and r['flag_evento_atipico'] == 'true')
    }
    ocorrencias = defaultdict(Counter)
    interrupcoes = defaultdict(Counter)
    for row in ler('ocorrencias_uc'):
        if (row['alimentador'], row['data_abertura'][:7]) in cobertura:
            ocorrencias[row['alimentador']][row['causa']] += 1
            interrupcoes[row['alimentador']][row['causa']] += row['flag_sobreposicao'] == 'false'
    assert {r['alimentador'] for r in ranking['ranking']} == {a for a, _ in cobertura}
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
@pytest.mark.parametrize('recorte,ucs', [({}, 240), ({'municipio': 'Recife'}, 60)])
async def test_exclusao_filtra_linhas_antes_de_agregar(client, headers, recorte, ucs):
    params = dict(sem_evento_atipico=True, **recorte)
    mes = await get(client, headers, 'serie', periodo='2025-07..2025-07', **params)
    ciclo = await get(client, headers, 'serie', periodo='2025-07..2025-08', **params)
    assert mes['totais']['numero_ucs'] == mes['serie'][0]['numero_ucs'] == ucs
    assert mes['serie'][0] == ciclo['serie'][0]
    assert ciclo['totais']['numero_ucs'] == ucs + 60
    for indicador in ('chi', 'interrupcoes'):
        assert sum(D(p[indicador]) for p in ciclo['serie']) == D(ciclo['totais'][indicador])
    ranking = await get(client, headers, 'ranking', periodo='2025-07..2025-07', **params)
    for campo in ('chi', 'interrupcoes', 'numero_ucs'):
        assert sum(D(r[campo]) for r in ranking['ranking']) == D(mes['totais'][campo])
    if recorte:
        # Só as 60 UCs do alimentador com competência válida permanecem.
        assert D(mes['totais']['dec']) == D(mes['totais']['fec']) == D('0.02')


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


@INTEGRATION
@pytest.mark.parametrize('sem_evento', [False, True])
@pytest.mark.parametrize('fim', ['2025-07', '2025-08'])
@pytest.mark.parametrize(
    'recorte',
    [
        {'bairro': 'Bairro sintético 1'},
        {'municipio': 'Recife', 'classe': 'Residencial'},
        {'alimentador': 'ALM-REC-001', 'classe': 'Comercial'},
        {'municipio': 'Recife', 'bairro': 'Bairro sintético 3'},
        {'bairro': 'Pina'},
    ],
)
async def test_recortes_por_uc_conferidos_contra_csv_e_kpis(
    client, headers, sem_evento, fim, recorte
):
    ucs = {r['id_uc']: r for r in ler('dim_uc') if all(r[k] == v for k, v in recorte.items())}
    alimentadores = {r['alimentador'] for r in ucs.values()}
    cobertura = {
        (r['alimentador'], r['competencia'])
        for r in ler('continuidade_alimentador_mensal')
        if '2025-07-01' <= r['competencia'] <= fim + '-01'
        and r['alimentador'] in alimentadores
        and not (sem_evento and r['flag_evento_atipico'] == 'true')
    }
    ocorrencias = [
        r
        for r in ler('ocorrencias_uc')
        if r['id_uc'] in ucs and (r['alimentador'], r['data_abertura'][:7] + '-01') in cobertura
    ]

    def conferir(valores, linhas, competencias):
        if not competencias:
            assert all(
                valores[k] is None for k in ('chi', 'interrupcoes', 'numero_ucs', 'dec', 'fec')
            )
            return
        minutos_por_mes = defaultdict(lambda: D(0))
        for linha in linhas:
            minutos_por_mes[linha['alimentador'], linha['data_abertura'][:7]] += D(
                linha['duracao_efetiva_min']
            )
        chi = sum((arredondar(v / 60) for v in minutos_por_mes.values()), D(0))
        interrupcoes = sum(r['flag_sobreposicao'] == 'false' for r in linhas)
        cobertos = {a for a, _ in competencias}
        denominador = sum(r['alimentador'] in cobertos for r in ucs.values())
        assert D(valores['chi']) == chi
        assert valores['chi'] == f'{chi:.2f}'
        assert valores['interrupcoes'] == interrupcoes
        assert valores['numero_ucs'] == denominador
        assert D(valores['dec']) == arredondar(chi / denominador)
        assert D(valores['fec']) == arredondar(D(interrupcoes) / denominador)

    params = dict(periodo=f'2025-07..{fim}', sem_evento_atipico=sem_evento, **recorte)
    serie = await get(client, headers, 'serie', **params)
    ranking = (await get(client, headers, 'ranking', **params))['ranking']
    conferir(serie['totais'], ocorrencias, cobertura)
    for ponto in serie['serie']:
        conferir(
            ponto,
            [r for r in ocorrencias if r['data_abertura'][:7] + '-01' == ponto['competencia']],
            {(a, mes) for a, mes in cobertura if mes == ponto['competencia']},
        )
    assert {r['alimentador'] for r in ranking} == {a for a, _ in cobertura}
    for item in ranking:
        linhas = [r for r in ocorrencias if r['alimentador'] == item['alimentador']]
        conferir(item, linhas, {(a, mes) for a, mes in cobertura if a == item['alimentador']})
        assert {r['causa']: r['ocorrencias'] for r in item['causas']} == Counter(
            r['causa'] for r in linhas
        )
        assert {r['causa']: r['interrupcoes'] for r in item['causas']} == {
            causa: sum(r['causa'] == causa and r['flag_sobreposicao'] == 'false' for r in linhas)
            for causa in {r['causa'] for r in linhas}
        }
    response = await client.get('/api/v1/kpis', headers=headers, params=params)
    assert response.status_code == 200, response.text
    assert response.json()['sem_evento_atipico'] is sem_evento
    for campo in ('dec', 'fec'):
        assert response.json()['continuidade'][campo]['valor'] == serie['totais'][campo]


@INTEGRATION
@pytest.mark.parametrize('recorte', [{}, {'classe': 'Residencial'}])
async def test_kpis_aplica_exclusao_tambem_na_comparacao(client, headers, recorte):
    params = dict(
        periodo='2026-01..2026-01',
        comparacao='2025-07..2025-07',
        sem_evento_atipico=True,
        **recorte,
    )
    response = await client.get('/api/v1/kpis', headers=headers, params=params)
    assert response.status_code == 200, response.text
    anterior = await get(
        client, headers, 'serie', periodo=params['comparacao'], sem_evento_atipico=True, **recorte
    )
    for campo in ('dec', 'fec'):
        assert response.json()['continuidade'][campo]['comparacao'] == anterior['totais'][campo]


@INTEGRATION
async def test_totais_reagregam_numeradores_antes_de_arredondar(client, headers):
    # 1/60 por mês arredonda a 0,02; 2/60 no período arredonda a 0,03.
    serie = await get(
        client, headers, 'serie', periodo='2025-08..2025-09', alimentador='ALM-REC-002'
    )
    for campo in ('chi', 'interrupcoes'):
        assert sum(D(p[campo]) for p in serie['serie']) == D(serie['totais'][campo])
    for campo in ('dec', 'fec'):
        assert sum(D(p[campo]) for p in serie['serie']) == D('0.04')
        assert D(serie['totais'][campo]) == D('0.03')


@INTEGRATION
@pytest.mark.parametrize('duracao,chi_mensal', [(D('1'), '0.02'), (D('0.30'), '0.01')])
async def test_chi_do_detalhe_arredonda_por_alimentador_e_competencia(
    client, headers, db, duracao, chi_mensal
):
    # Este alimentador tem uma UC. Dois meses de 1 minuto devem somar 0,04 h,
    # como a Gold, em vez de arredondar a soma dos minutos para 0,03 h.
    alimentador = 'ALM-OLI-006'
    uc = next(r for r in ler('dim_uc') if r['alimentador'] == alimentador)
    mensais = await db.fetch("""
        SELECT * FROM analytics.continuidade_alimentador_mensal
        WHERE alimentador = 'ALM-OLI-006' AND competencia BETWEEN '2025-08-01' AND '2025-09-01'
    """)
    ocorrencias = await db.fetch("""
        SELECT * FROM analytics.ocorrencias_uc WHERE alimentador = 'ALM-OLI-006'
        AND data_abertura >= '2025-08-01' AND data_abertura < '2025-10-01'
    """)
    try:
        await db.execute(
            """
            UPDATE analytics.continuidade_alimentador_mensal SET chi_horas=$1, dec=$1
            WHERE alimentador = 'ALM-OLI-006'
              AND competencia BETWEEN '2025-08-01' AND '2025-09-01'
        """,
            D(chi_mensal),
        )
        await db.execute(
            """
            UPDATE analytics.ocorrencias_uc SET duracao_min=$1, duracao_efetiva_min=$1,
                data_encerramento=data_abertura + ($1::numeric * interval '1 minute')
            WHERE alimentador = 'ALM-OLI-006'
              AND data_abertura >= '2025-08-01' AND data_abertura < '2025-10-01'
        """,
            duracao,
        )
        esperado = D(chi_mensal) * 2
        for recorte in ({}, {'bairro': uc['bairro']}, {'classe': uc['classe']}):
            params = dict(periodo='2025-08..2025-09', alimentador=alimentador, **recorte)
            serie = await get(client, headers, 'serie', **params)
            assert serie['totais']['chi'] == f'{esperado:.2f}'
            assert [p['chi'] for p in serie['serie']] == [chi_mensal, chi_mensal]
            ranking = (await get(client, headers, 'ranking', **params))['ranking']
            assert ranking[0]['chi'] == f'{esperado:.2f}'
            assert D(ranking[0]['dec']) == esperado
            response = await client.get('/api/v1/kpis', headers=headers, params=params)
            assert response.status_code == 200, response.text
            assert D(response.json()['continuidade']['dec']['valor']) == esperado
    finally:
        await db.executemany(
            """
            UPDATE analytics.continuidade_alimentador_mensal SET chi_horas=$1, dec=$2
            WHERE alimentador=$3 AND competencia=$4
        """,
            [(r['chi_horas'], r['dec'], alimentador, r['competencia']) for r in mensais],
        )
        await db.executemany(
            """
            UPDATE analytics.ocorrencias_uc SET duracao_min=$1, duracao_efetiva_min=$2,
                data_encerramento=$3 WHERE id_ocorrencia=$4
        """,
            [
                (
                    r['duracao_min'],
                    r['duracao_efetiva_min'],
                    r['data_encerramento'],
                    r['id_ocorrencia'],
                )
                for r in ocorrencias
            ],
        )


@INTEGRATION
@pytest.mark.parametrize('sem_evento', [False, True])
@pytest.mark.parametrize('recorte', [{}, {'municipio': 'Recife', 'classe': 'Residencial'}])
async def test_comparacao_calcula_serie_ranking_e_causas(client, headers, sem_evento, recorte):
    params = dict(
        periodo='2026-01..2026-02',
        comparacao='2025-07..2025-08',
        sem_evento_atipico=sem_evento,
        **recorte,
    )
    atual = await get(client, headers, 'serie', **params)
    anterior = await get(
        client,
        headers,
        'serie',
        periodo=params['comparacao'],
        sem_evento_atipico=sem_evento,
        **recorte,
    )
    assert atual['dados_comparacao'] == {k: anterior[k] for k in ('totais', 'serie')}
    for ordem in ('chi', 'dec', 'fec'):
        ranking = await get(client, headers, 'ranking', ordem=ordem, **params)
        esperado = await get(
            client,
            headers,
            'ranking',
            periodo=params['comparacao'],
            ordem=ordem,
            sem_evento_atipico=sem_evento,
            **recorte,
        )
        assert ranking['ranking_comparacao'] == esperado['ranking']


@INTEGRATION
async def test_comparacao_ausente_e_comparacao_sem_observacoes(client, headers):
    primeiro = await get(client, headers, 'serie', periodo='2022-07..2022-07')
    assert primeiro['comparacao'] is primeiro['dados_comparacao'] is None
    ranking = await get(client, headers, 'ranking', periodo='2022-07..2022-07')
    assert ranking['comparacao'] is ranking['ranking_comparacao'] is None
    params = dict(
        periodo='2025-08..2025-08',
        comparacao='2025-07..2025-07',
        sem_evento_atipico=True,
        alimentador='ALM-REC-001',
    )
    serie = await get(client, headers, 'serie', **params)
    assert serie['totais']['chi'] is not None
    assert all(v is None for v in serie['dados_comparacao']['totais'].values())
    assert serie['dados_comparacao']['serie'][0]['chi'] is None
    assert (await get(client, headers, 'ranking', **params))['ranking_comparacao'] == []
