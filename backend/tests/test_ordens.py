import asyncio
import json
from datetime import date, timedelta

import asyncpg
import pytest

pytestmark = pytest.mark.integration
BASE = '/api/v1/ordens-inspecao'


async def criar(client, headers, uc='UC100001'):
    response = await client.post(BASE, headers=headers, json={'ucs': [uc]})
    assert response.status_code == 201, response.text
    return response.json()['criadas'][0]['id']


async def test_batch_snapshot_and_database_uniqueness(client, headers, db):
    response = await client.post(
        BASE, headers=headers, json={'ucs': ['UC100001', 'UC100001', 'UC999999']}
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data['criadas']) == 1
    assert len(data['rejeitadas']) == 2
    ordem = data['criadas'][0]
    assert ordem['status'] == 'ABERTA' and ordem['energia_recuperar_kwh'] == '101.00'
    assert await db.fetchval('SELECT count(*) FROM operations.ordem_eventos') == 1
    with pytest.raises(asyncpg.UniqueViolationError):
        await db.execute("""INSERT INTO operations.ordens_inspecao
            SELECT gen_random_uuid(),id_uc,status,score,motivos,energia_recuperar_kwh,
            energia_recuperar_reais,inspetor,resultado,tipo_irregularidade,kwh_recuperado,
            motivo_cancelamento,criado_por,atualizado_por,criado_em,atualizado_em
            FROM operations.ordens_inspecao""")
    listed = await client.get(BASE + '?size=1', headers=headers)
    assert listed.json()['total'] == 1
    assert (await client.get(BASE + '?size=101', headers=headers)).status_code == 422


@pytest.mark.parametrize('irregular', [True, False])
async def test_full_cycle(client, headers, db, irregular):
    id_ = await criar(client, headers)
    url = f'{BASE}/{id_}'
    assert (
        await client.post(url + '/despachar', headers=headers, json={'inspetor': 'INSP-040'})
    ).json()['status'] == 'EM_CAMPO'
    assert (
        await client.post(
            url + '/tentativas', headers=headers, json={'observacao': 'Imóvel fechado'}
        )
    ).json()['status'] == 'ABERTA'
    tentativa = json.loads(
        await db.fetchval("SELECT dados FROM operations.ordem_eventos WHERE tipo='TENTATIVAS'")
    )
    assert tentativa == {'observacao': 'Imóvel fechado', 'inspetor': 'INSP-040'}
    await client.post(url + '/despachar', headers=headers, json={'inspetor': 'INSP-002'})
    body = dict(
        resultado='IRREGULARIDADE CONFIRMADA' if irregular else 'SEM IRREGULARIDADE',
        tipo_irregularidade='DESVIO DIRETO' if irregular else None,
        kwh_recuperado='125.50' if irregular else '0',
        data='2026-06-20',
    )
    result = await client.post(url + '/resultado', headers=headers, json=body)
    assert result.status_code == 200, result.text
    assert result.json()['status'] == 'CONCLUIDA'
    inspection = await db.fetchrow('SELECT * FROM operations.inspecoes')
    assert inspection['inspetor'] == 'INSP-002'
    assert inspection['resultado'] == body['resultado']
    assert await db.fetchval('SELECT count(*) FROM operations.ordem_eventos') == 5
    assert await db.fetchval("SELECT count(*) FROM ai_read.inspecoes WHERE origem='portal'") == 1
    # Reinspeção permitida após conclusão.
    assert await criar(client, headers) != id_


async def test_future_result_preserves_order_and_audit(client, headers, db):
    id_ = await criar(client, headers)
    url = f'{BASE}/{id_}'
    await client.post(url + '/despachar', headers=headers, json={'inspetor': 'INSP-001'})
    response = await client.post(
        url + '/resultado',
        headers=headers,
        json={
            'resultado': 'SEM IRREGULARIDADE',
            'kwh_recuperado': 0,
            'data': (date.today() + timedelta(days=1)).isoformat(),
        },
    )
    assert response.status_code == 422
    assert await db.fetchval('SELECT status FROM operations.ordens_inspecao') == 'EM_CAMPO'
    assert await db.fetchval('SELECT count(*) FROM operations.inspecoes') == 0
    assert await db.fetchval('SELECT count(*) FROM operations.ordem_eventos') == 2


@pytest.mark.parametrize('state', ['ABERTA', 'EM_CAMPO'])
async def test_cancel(client, headers, db, state):
    id_ = await criar(client, headers)
    if state == 'EM_CAMPO':
        await client.post(f'{BASE}/{id_}/despachar', headers=headers, json={'inspetor': 'INSP-001'})
    result = await client.post(
        f'{BASE}/{id_}/cancelar', headers=headers, json={'motivo': 'Solicitação duplicada'}
    )
    assert result.json()['status'] == 'CANCELADA'
    assert await db.fetchval('SELECT count(*) FROM operations.inspecoes') == 0
    assert await criar(client, headers) != id_


@pytest.mark.parametrize(
    'state,action',
    [
        ('ABERTA', 'tentativas'),
        ('ABERTA', 'resultado'),
        ('EM_CAMPO', 'despachar'),
        *[
            (s, a)
            for s in ['CONCLUIDA', 'CANCELADA']
            for a in ['despachar', 'tentativas', 'resultado', 'cancelar']
        ],
    ],
)
async def test_invalid_transition_is_atomic(client, headers, db, state, action):
    id_ = await criar(client, headers)
    url = f'{BASE}/{id_}'
    if state in ('EM_CAMPO', 'CONCLUIDA'):
        await client.post(url + '/despachar', headers=headers, json={'inspetor': 'INSP-001'})
    if state == 'CONCLUIDA':
        await client.post(
            url + '/resultado',
            headers=headers,
            json={'resultado': 'SEM IRREGULARIDADE', 'kwh_recuperado': 0, 'data': '2026-06-20'},
        )
    if state == 'CANCELADA':
        await client.post(url + '/cancelar', headers=headers, json={'motivo': 'Teste'})
    before = await db.fetch('SELECT * FROM operations.ordem_eventos ORDER BY id')
    bodies = dict(
        despachar={'inspetor': 'INSP-001'},
        tentativas={'observacao': 'Teste'},
        resultado={'resultado': 'SEM IRREGULARIDADE', 'kwh_recuperado': 0, 'data': '2026-06-20'},
        cancelar={'motivo': 'Teste'},
    )
    response = await client.post(url + '/' + action, headers=headers, json=bodies[action])
    assert response.status_code == 409
    assert before == await db.fetch('SELECT * FROM operations.ordem_eventos ORDER BY id')


@pytest.mark.parametrize('cargo', ['diretoria', 'comercial', 'atendimento', 'operacao'])
async def test_write_roles(client, cargo, headers):
    id_ = await criar(client, headers)
    token = (
        await client.post(
            '/api/v1/auth/login', json={'login': cargo, 'senha': 'Demo-Venergy-2026!'}
        )
    ).json()['access_token']
    other = {'Authorization': 'Bearer ' + token}
    assert (await client.get(BASE, headers=other)).status_code == 200
    calls = [
        ('', {'ucs': ['UC100002']}),
        (f'/{id_}/despachar', {'inspetor': 'INSP-001'}),
        (f'/{id_}/tentativas', {'observacao': 'Teste'}),
        (
            f'/{id_}/resultado',
            {'resultado': 'SEM IRREGULARIDADE', 'kwh_recuperado': 0, 'data': '2026-06-20'},
        ),
        (f'/{id_}/cancelar', {'motivo': 'Teste'}),
    ]
    for suffix, body in calls:
        assert (await client.post(BASE + suffix, headers=other, json=body)).status_code == 403


async def test_concurrent_order_creation(client, headers, db):
    async def request():
        return await client.post(BASE, headers=headers, json={'ucs': ['UC100001']})

    responses = await asyncio.gather(request(), request())
    assert all(r.status_code == 201 for r in responses)
    assert sorted(len(r.json()['criadas']) for r in responses) == [0, 1]
    assert await db.fetchval('SELECT count(*) FROM operations.ordem_eventos') == 1


async def test_audit_failure_rolls_back_transition(client, headers, db):
    id_ = await criar(client, headers)
    await db.execute('REVOKE INSERT ON operations.ordem_eventos FROM portal')
    try:
        response = await client.post(
            f'{BASE}/{id_}/despachar', headers=headers, json={'inspetor': 'INSP-001'}
        )
        assert response.status_code == 500
        assert await db.fetchval('SELECT status FROM operations.ordens_inspecao') == 'ABERTA'
    finally:
        await db.execute('GRANT INSERT ON operations.ordem_eventos TO portal')
