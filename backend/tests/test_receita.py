from decimal import Decimal as D

import pytest

from app.core.decomposicao import decompor
from app.modules.receita.service import somar_efeitos

P = '2025-07..2026-06'


def linha(q0, r0, t0, b0, q1, r1, t1, b1):
    return dict(
        zip(
            ('q0', 'r0', 't0', 'b0', 'q1', 'r1', 't1', 'b1'),
            map(D, (q0, r0, t0, b0, q1, r1, t1, b1)),
        )
    )


def test_soma_por_subgrao_difere_de_decompor_total():
    linhas = [linha(10, 5, 5, 0, 0, 0, 0, 0), linha(10, 10, 10, 0, 20, 20, 20, 0)]
    resultado = somar_efeitos(linhas, lambda _: ())[()]
    assert resultado.volume == D('5.00')  # -10 × 0,50 + 10 × 1,00
    assert resultado.mix == 0
    assert decompor(D(20), D(15), D(15), D(0), D(20), D(20), D(20), D(0)).volume == 0
    assert resultado.volume + resultado.reajuste + resultado.bandeira + resultado.mix == 5


@pytest.mark.parametrize(
    'valores,volume,mix',
    [
        ((0, 10, 0, 0, 0, 20, 0, 0), '10', '0'),
        ((10, 10, 0, 0, 0, 20, 0, 0), '10', '0'),
        ((10, 10, 10, 0, 0, 20, 0, 0), '-10', '20'),
        ((0, 0, 0, 0, 10, 20, 20, 0), '20', '0'),
    ],
)
def test_bordas(valores, volume, mix):
    total = somar_efeitos([linha(*valores)], lambda _: ())[()]
    assert total.volume == D(volume)
    assert total.mix == D(mix)
    assert total.volume + total.reajuste + total.bandeira + total.mix == (
        total.receita_atual - total.receita_base
    )


async def get(client, headers, rota, **params):
    response = await client.get('/api/v1/' + rota, headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.integration
async def test_valores_r5_e_r3(client, headers):
    params = dict(
        periodo='2025-07..2025-07',
        comparacao='2025-06..2025-06',
        municipio='Recife',
        classe='Residencial',
    )
    data = await get(client, headers, 'receita/decomposicao', **params)
    assert D(data['receita_base']) == D('2324.00')
    assert D(data['receita_atual']) == D('2386.80')
    assert {k: D(v) for k, v in data['efeitos'].items()} == dict(
        volume=D('-202.40'), reajuste=D(0), bandeira=D('265.20'), mix=D(0)
    )
    params.update(
        periodo='2025-08..2025-08', comparacao='2025-07..2025-07', bairro='Bairro sintético 2'
    )
    data = await get(client, headers, 'receita/decomposicao', **params)
    # DEMAIS: (1272-1362)*0,90=-81; bandeira -127,20. Entrada: +48.
    assert D(data['variacao']) == D('-160.20')
    assert {k: D(v) for k, v in data['efeitos'].items()} == dict(
        volume=D('-33.00'), reajuste=D(0), bandeira=D('-127.20'), mix=D(0)
    )
    grupos = (await get(client, headers, 'receita/grupos', **params))['itens']
    assert [g['grupo_uc'] for g in grupos] == ['GD', 'IRREGULARIDADE_CONFIRMADA', 'DEMAIS']
    for g, esperado in zip(
        grupos, [(0, 0, 0, 0), (0, 60, 0, 48), (1362, 1272, '1225.80', '1017.60')]
    ):
        assert tuple(
            D(g[k])
            for k in ('volume_base_kwh', 'volume_atual_kwh', 'receita_base', 'receita_atual')
        ) == tuple(map(D, esperado))


@pytest.mark.integration
@pytest.mark.parametrize(
    'recorte',
    [
        {},
        {'municipio': 'Recife'},
        {'municipio': 'Recife', 'classe': 'Residencial'},
        {'bairro': 'Bairro sintético 1'},
    ],
)
async def test_kpis_fechamento_e_grupos(client, headers, recorte):
    params = dict(periodo=P, **recorte)
    data = await get(client, headers, 'receita/decomposicao', **params)
    kpis = await get(client, headers, 'kpis', **params)
    assert sum(D(v) for v in data['efeitos'].values()) == D(data['variacao'])
    for kpi, atual, base in [
        ('receita', 'receita_atual', 'receita_base'),
        ('volume_faturado_kwh', 'volume_atual_kwh', 'volume_base_kwh'),
    ]:
        assert D(kpis[kpi]['valor']) == D(data[atual])
        assert D(kpis[kpi]['comparacao']) == D(data[base])
    grupos = (await get(client, headers, 'receita/grupos', **params))['itens']
    for campo in ('receita_base', 'receita_atual', 'volume_base_kwh', 'volume_atual_kwh'):
        assert sum(D(g[campo]) for g in grupos) == D(data[campo])


@pytest.mark.integration
@pytest.mark.parametrize('nivel,recorte', [('municipio', {}), ('bairro', {'municipio': 'Recife'})])
async def test_aditividade_locais(client, headers, nivel, recorte):
    params = dict(periodo=P, **recorte)
    data = await get(client, headers, 'receita/decomposicao', **params)
    locais = await get(client, headers, 'receita/locais', nivel=nivel, **params)
    assert locais['total'] == data
    for campo in ('receita_base', 'receita_atual', 'volume_base_kwh', 'volume_atual_kwh'):
        assert sum(D(item[campo]) for item in locais['itens']) == D(data[campo])
    for campo in data['efeitos']:
        assert sum(D(item['efeitos'][campo]) for item in locais['itens']) == D(
            data['efeitos'][campo]
        )
    assert [
        (D(i['variacao']), i['municipio'], i['bairro'] or '') for i in locais['itens']
    ] == sorted((D(i['variacao']), i['municipio'], i['bairro'] or '') for i in locais['itens'])


@pytest.mark.integration
async def test_erros_e_vazio(client, headers):
    url = '/api/v1/receita/'
    for rota in ('decomposicao', 'locais', 'grupos'):
        extras = {'nivel': 'municipio'} if rota == 'locais' else {}
        response = await client.get(url + rota, params={'periodo': P, **extras})
        assert response.status_code == 401
        assert set(response.json()) == {'detail', 'code'}
        for params, code in [
            ({'periodo': 'invalido', 'alimentador': ''}, 'RECORTE_INVALIDO'),
            ({'periodo': '2022-07..2022-07'}, 'COMPARACAO_INDISPONIVEL'),
            ({'periodo': 'invalido'}, 'PERIODO_INVALIDO'),
        ]:
            response = await client.get(url + rota, headers=headers, params={**extras, **params})
            assert response.status_code == 422 and set(response.json()) == {'detail', 'code'}
            assert response.json()['code'] == code
    response = await client.get(
        url + 'locais', headers=headers, params={'periodo': P, 'nivel': 'classe', 'alimentador': ''}
    )
    assert response.status_code == 422 and response.json()['code'] == 'VALIDACAO_INVALIDA'
    assert set(response.json()) == {'detail', 'code'}
    params = dict(periodo=P, municipio='inexistente')
    data = await get(client, headers, 'receita/decomposicao', **params)
    assert D(data['receita_atual']) == D(data['receita_base']) == 0
    assert data['variacao_pct'] is data['variacao_volume_pct'] is None
    assert all(D(v) == 0 for v in data['efeitos'].values())
    locais = await get(client, headers, 'receita/locais', nivel='bairro', **params)
    assert locais['itens'] == [] and locais['total'] == data
    grupos = (await get(client, headers, 'receita/grupos', **params))['itens']
    assert len(grupos) == 3 and all(D(g['receita_atual']) == 0 for g in grupos)


@pytest.mark.integration
async def test_periodos_sobrepostos(client, headers):
    data = await get(
        client,
        headers,
        'receita/decomposicao',
        periodo='2025-07..2025-08',
        comparacao='2025-07..2025-08',
    )
    assert D(data['variacao']) == 0
    assert all(D(v) == 0 for v in data['efeitos'].values())
