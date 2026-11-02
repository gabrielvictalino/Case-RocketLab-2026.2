import re
import time
from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration
BASE = '/api/v1/ucs'


async def test_endpoint_resolution_and_errors(client, headers):
    # P13-1: uc100005 e 100005 -> 200 com id_uc='UC100005'
    res1 = await client.get(f'{BASE}/uc100005', headers=headers)
    assert res1.status_code == 200
    assert res1.json()['id_uc'] == 'UC100005'

    res2 = await client.get(f'{BASE}/100005', headers=headers)
    assert res2.status_code == 200
    assert res2.json()['id_uc'] == 'UC100005'

    # UC999999 -> 404 UC_NAO_ENCONTRADA
    res_not_found = await client.get(f'{BASE}/UC999999', headers=headers)
    assert res_not_found.status_code == 404
    assert res_not_found.json()['code'] == 'UC_NAO_ENCONTRADA'

    # abc -> 422 UC_INVALIDA
    res_invalid = await client.get(f'{BASE}/abc', headers=headers)
    assert res_invalid.status_code == 422
    assert res_invalid.json()['code'] == 'UC_INVALIDA'

    # sem token -> 401
    res_no_auth = await client.get(f'{BASE}/UC100005')
    assert res_no_auth.status_code == 401


async def test_documento_mascarado_and_no_original(client, headers):
    # P13-2: documento vem mascarado e o JSON não contém a chave consumo_kwh_original
    res = await client.get(f'{BASE}/UC100000', headers=headers)
    assert res.status_code == 200
    body_text = res.text
    assert 'consumo_kwh_original' not in body_text
    doc = res.json()['cabecalho']['documento']
    assert bool(
        re.fullmatch(r'\*{3}\.\d{3}\.\d{3}-\*{2}', doc)
        or re.fullmatch(r'\*{2}\.\d{3}\.\d{3}/\d{4}-\*{2}', doc)
    )


async def test_uc_com_gd_e_sem_gd(client, headers):
    # P13-3: UC com GD (UC100000): cabecalho.gd = {potencia_kw: 5, data_conexao: 2025-01-01}
    # UC sem GD -> gd = None
    res_gd = await client.get(f'{BASE}/UC100000', headers=headers)
    assert res_gd.status_code == 200
    gd = res_gd.json()['cabecalho']['gd']
    assert gd is not None
    assert Decimal(str(gd['potencia_kw'])) == Decimal('5')
    assert gd['data_conexao'] == '2025-01-01'

    res_no_gd = await client.get(f'{BASE}/UC100001', headers=headers)
    assert res_no_gd.status_code == 200
    assert res_no_gd.json()['cabecalho']['gd'] is None


async def test_uc_troca_medidor(client, headers):
    # P13-4: UC com troca (UC100001): ponto de 2025-09 tem troca_medidor=true
    # e consumo_ajustado=true; medidor_atual = MD999999
    res = await client.get(f'{BASE}/UC100001', headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data['cabecalho']['medidor_atual']['id_medidor'] == 'MD999999'
    assert data['cabecalho']['medidor_atual']['data_instalacao'] == '2025-09-01'

    # Verifica ponto de 2025-09 no bloco consumo
    pontos_2025_09 = [
        m['atual'] for m in data['consumo']['meses'] if m['competencia'] == '2025-09-01'
    ]
    assert len(pontos_2025_09) == 1
    ponto = pontos_2025_09[0]
    assert ponto['troca_medidor'] is True
    assert ponto['consumo_ajustado'] is True


async def test_consumo_12_meses_e_leitura_estimada(client, headers):
    # P13-5: consumo com exatamente 12 meses crescentes (2025-07..2026-06 na amostra),
    # com anterior em 2024-07..2025-06
    res = await client.get(f'{BASE}/UC100000', headers=headers)
    assert res.status_code == 200
    consumo = res.json()['consumo']
    meses = consumo['meses']
    assert len(meses) == 12
    comps = [m['competencia'] for m in meses]
    assert comps == sorted(comps)
    assert comps[0] == '2025-07-01'
    assert comps[-1] == '2026-06-01'
    for m in meses:
        assert m['atual'] is not None
        assert m['anterior'] is not None

    # UC nova (UC100298, 12 linhas) -> anterior = None em todos
    res_nova = await client.get(f'{BASE}/UC100298', headers=headers)
    assert res_nova.status_code == 200
    for m in res_nova.json()['consumo']['meses']:
        assert m['atual'] is not None
        assert m['anterior'] is None

    # Leitura estimada de UC100002 em 2026-06 marcada
    res_est = await client.get(f'{BASE}/UC100002', headers=headers)
    assert res_est.status_code == 200
    ponto_jun = [
        m['atual'] for m in res_est.json()['consumo']['meses'] if m['competencia'] == '2026-06-01'
    ][0]
    assert ponto_jun['leitura_estimada'] is True


async def test_faturas_em_aberto_dias_atraso(client, headers):
    # P13-6: faturas em aberto de UC100003 (3, decrescentes) com dias_atraso = 11, 42, 72
    res = await client.get(f'{BASE}/UC100003', headers=headers)
    assert res.status_code == 200
    faturas = res.json()['faturas_abertas']
    assert len(faturas) == 3
    comps = [f['competencia'] for f in faturas]
    assert comps == ['2026-06-01', '2026-05-01', '2026-04-01']
    atrasos = [f['dias_atraso'] for f in faturas]
    assert atrasos == [11, 42, 72]


async def test_interrupcoes_e_resumo_alimentador(client, headers):
    # P13-7: interrupções da UC na janela e resumo do alimentador:
    # UC100000 (ALM-REC-001, 2025-07..2026-06) -> ocorrencias=12, dec=3.52 (211 ÷ 60).
    # Afirma que NÃO é 3.55 (a soma dos DEC mensais).
    res = await client.get(f'{BASE}/UC100000', headers=headers)
    assert res.status_code == 200
    interrupcoes = res.json()['interrupcoes']
    alm = interrupcoes['alimentador']
    assert alm['alimentador'] == 'ALM-REC-001'
    assert alm['ocorrencias'] == 12
    assert Decimal(str(alm['dec'])) == Decimal('3.52')
    assert Decimal(str(alm['dec'])) != Decimal('3.55')
    assert len(interrupcoes['ocorrencias']) == 12


async def test_chamados_inspecoes_e_ordem_ativa(client, headers):
    # P13-8: chamados ordenados, nota nula -> None (UC100001);
    # inspeções de portal_read.inspecoes com origem;
    # ordem_ativa presente após criar pela API e None sem ordem
    res1 = await client.get(f'{BASE}/UC100001', headers=headers)
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1['ordem_ativa'] is None

    # Chamado de UC100001 tem nota nula -> None
    chamados = data1['chamados']
    assert len(chamados) >= 1
    assert chamados[0]['nota'] is None
    for ch in chamados:
        seqs = [h['sequencia'] for h in ch['historico']]
        assert seqs == sorted(seqs)
        assert len(seqs) >= 1

    # Inspeções com origem
    inspecoes = data1['inspecoes']
    assert len(inspecoes) >= 1
    assert inspecoes[0]['origem'] in ('historica', 'portal')

    # Cria ordem pela API e confere se ordem_ativa passa a existir
    cria_res = await client.post(
        '/api/v1/ordens-inspecao', headers=headers, json={'ucs': ['UC100001']}
    )
    assert cria_res.status_code == 201

    res2 = await client.get(f'{BASE}/UC100001', headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2['ordem_ativa'] is not None
    assert data2['ordem_ativa']['id_uc'] == 'UC100001'
    assert data2['ordem_ativa']['status'] == 'ABERTA'


async def test_explicacao_conta_casos_endpoint(client, headers):
    # P14-3: UC100004 compara 2026-05 x 2025-05 (pula a competência 2026-06 sem fatura)
    res_04 = await client.get(f'{BASE}/UC100004', headers=headers)
    assert res_04.status_code == 200
    exp_04 = res_04.json()['explicacao_conta']
    assert exp_04['situacao'] == 'COMPARADA'
    assert exp_04['atual']['competencia'] == '2026-05-01'
    assert exp_04['anterior']['competencia'] == '2025-05-01'

    # UC100298 -> SEM_BASE
    res_298 = await client.get(f'{BASE}/UC100298', headers=headers)
    assert res_298.status_code == 200
    exp_298 = res_298.json()['explicacao_conta']
    assert exp_298['situacao'] == 'SEM_BASE'
    assert 'Não há fatura' in exp_298['frase']


async def test_sla_performance(client, headers):
    # P13-9: resposta em < 300 ms com a amostra (time.perf_counter após aquecimento)
    # Chamada de aquecimento
    warmup = await client.get(f'{BASE}/UC100000', headers=headers)
    assert warmup.status_code == 200

    # Chamada medida
    inicio = time.perf_counter()
    res = await client.get(f'{BASE}/UC100000', headers=headers)
    duracao_ms = (time.perf_counter() - inicio) * 1000
    assert res.status_code == 200
    assert duracao_ms < 300
