from decimal import Decimal

import pytest

pytestmark = pytest.mark.integration
FILA = '/api/v1/perdas/fila'
ORDENS = '/api/v1/ordens-inspecao'


def totais(itens, kwh, reais):
    return {'itens': itens, 'energia_recuperar_kwh': kwh, 'energia_recuperar_reais': reais}


async def obter(client, headers, **params):
    response = await client.get(FILA, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


async def criar(client, headers, uc):
    r = await client.post(ORDENS, headers=headers, json={'ucs': [uc]})
    assert r.status_code == 201, r.text
    return ORDENS + '/' + r.json()['criadas'][0]['id']


async def concluir(client, headers, uc, data):
    url = await criar(client, headers, uc)
    assert (
        await client.post(url + '/despachar', headers=headers, json={'inspetor': 'INSP-001'})
    ).status_code == 200
    response = await client.post(
        url + '/resultado',
        headers=headers,
        json={
            'resultado': 'SEM IRREGULARIDADE',
            'kwh_recuperado': 0,
            'data': data,
        },
    )
    assert response.status_code == 200, response.text


async def test_paginas_e_validacao(client, headers):
    dados = await obter(client, headers)
    assert dados['total'] == 12
    assert [dados['items'][0]['id_uc'], dados['items'][-1]['id_uc']] == ['UC100001', 'UC100012']
    filtro = totais(12, '1278.00', '1038.00')
    assert dados['totais']['filtro'] == filtro
    assert not {'titular', 'documento_mascarado', 'endereco'} & dados['items'][0].keys()
    for page, ids, pagina in [
        (
            1,
            ['UC100001', 'UC100002', 'UC100003', 'UC100004', 'UC100005'],
            totais(5, '515.00', '415.00'),
        ),
        (3, ['UC100011', 'UC100012'], totais(2, '223.00', '183.00')),
        (4, [], totais(0, '0.00', '0.00')),
        (1000000, [], totais(0, '0.00', '0.00')),
    ]:
        dados = await obter(client, headers, size=5, page=page)
        assert [item['id_uc'] for item in dados['items']] == ids
        assert dados['totais'] == {'pagina': pagina, 'filtro': filtro}
    for params in ({'size': 101}, {'page': 0}, {'page': 1000001}):
        r = await client.get(FILA, headers=headers, params=params)
        assert r.status_code == 422 and r.json()['code'] == 'VALIDACAO_INVALIDA'


@pytest.mark.parametrize(
    ('params', 'ids', 'kwh', 'reais'),
    [
        ({'municipio': 'Recife'}, None, '533.00', '433.00'),
        (
            {'municipio': 'Recife', 'classe': 'Comercial'},
            ['UC100005', 'UC100006'],
            '211.00',
            '171.00',
        ),
        (
            {'bairro': 'Bairro sintético 3'},
            ['UC100002', 'UC100007', 'UC100012'],
            '321.00',
            '261.00',
        ),
        ({'municipio': ''}, [], '0.00', '0.00'),
        ({'municipio': 'recife'}, [], '0.00', '0.00'),
        ({'municipio': 'inexistente'}, [], '0.00', '0.00'),
    ],
)
async def test_filtros(client, headers, params, ids, kwh, reais):
    dados = await obter(client, headers, **params)
    if ids is not None:
        assert [i['id_uc'] for i in dados['items']] == ids
    else:
        assert dados['total'] == 5
    assert dados['totais']['filtro'] == totais(dados['total'], kwh, reais)


async def test_ordem_ativa_e_cancelamento(client, headers):
    url = await criar(client, headers, 'UC100001')
    for etapa in ('aberta', 'campo'):
        if etapa == 'campo':
            assert (
                await client.post(
                    url + '/despachar', headers=headers, json={'inspetor': 'INSP-001'}
                )
            ).status_code == 200
        dados = await obter(client, headers)
        assert dados['totais']['filtro'] == totais(11, '1177.00', '957.00')
        assert dados['items'][0]['id_uc'] == 'UC100002'
    assert (
        await client.post(url + '/cancelar', headers=headers, json={'motivo': 'Teste'})
    ).status_code == 200
    assert (await obter(client, headers))['total'] == 12


async def test_inspecoes(client, headers):
    items = (await obter(client, headers))['items']
    anterior = items[0]['inspecao_anterior']
    assert anterior['id_inspecao'] == 'IN0000000'
    assert anterior['resultado'] == 'IRREGULARIDADE CONFIRMADA'
    assert anterior['tipo_irregularidade'] == 'DESVIO DIRETO'
    assert anterior['kwh_recuperado'] == '100.00' and anterior['origem'] == 'historica'
    assert items[1]['inspecao_anterior']['id_inspecao'] == 'IN0000001'
    assert items[1]['inspecao_anterior']['resultado'] == 'SEM IRREGULARIDADE'
    assert items[2]['inspecao_anterior'] is None
    await concluir(client, headers, 'UC100003', '2026-06-20')
    assert (await obter(client, headers))['items'][2]['inspecao_anterior']['origem'] == 'portal'
    await concluir(client, headers, 'UC100001', '2025-08-10')
    assert (await obter(client, headers))['items'][0]['inspecao_anterior']['origem'] == 'portal'


async def test_empate_score(client, headers, db):
    original = await db.fetchval("SELECT score FROM analytics.fila_inspecao WHERE id_uc='UC100002'")
    try:
        await db.execute(
            "UPDATE analytics.fila_inspecao SET score=$1 WHERE id_uc='UC100002'", Decimal('100')
        )
        a = await obter(client, headers, size=1, page=1)
        b = await obter(client, headers, size=1, page=2)
        assert [a['items'][0]['id_uc'], b['items'][0]['id_uc']] == ['UC100001', 'UC100002']
    finally:
        await db.execute(
            "UPDATE analytics.fila_inspecao SET score=$1 WHERE id_uc='UC100002'", original
        )


async def test_acesso(client):
    assert (await client.get(FILA)).status_code == 401
    token = (
        await client.post(
            '/api/v1/auth/login', json={'login': 'diretoria', 'senha': 'Demo-Venergy-2026!'}
        )
    ).json()['access_token']
    assert (await client.get(FILA, headers={'Authorization': 'Bearer ' + token})).status_code == 200
