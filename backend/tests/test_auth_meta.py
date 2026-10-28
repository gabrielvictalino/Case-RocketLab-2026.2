from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis

from app.main import create_app

pytestmark = pytest.mark.integration


async def test_health_login_meta_and_periods(client, headers, infrastructure):
    health = await client.get('/api/v1/health', headers={'X-Request-ID': 'teste-123'})
    assert health.status_code == 200
    assert health.json() == {'status': 'ok', 'postgres': 'ok', 'redis': 'ok'}
    assert health.headers['X-Request-ID'] == 'teste-123'
    carga = await client.get('/api/v1/meta/carga', headers=headers)
    assert carga.status_code == 200
    assert carga.json()['sintetica'] is True
    assert carga.json()['competencia_mais_recente'] == '2026-06-01'
    redis = Redis.from_url(infrastructure['settings'].redis_url)
    try:
        assert (await redis.get('versao_carga')).decode() == carga.json()['id']
    finally:
        await redis.aclose()
    filtros = await client.get('/api/v1/meta/filtros', headers=headers)
    assert len(filtros.json()['municipios']) == 3
    assert len(filtros.json()['classes']) == 5
    assert len(filtros.json()['alimentadores']) == 6
    for query in (
        'periodo=2025-13..2026-06',
        'periodo=2021-01..2021-12',
        'comparacao=2024-07..2025-06',
        'periodo=2022-07..2023-06',
    ):
        response = await client.get('/api/v1/meta/filtros?' + query, headers=headers)
        assert response.status_code == 422
        assert response.json()['code'].startswith('PERIODO')
    valid = await client.get('/api/v1/meta/filtros?periodo=2025-07..2026-06', headers=headers)
    assert valid.status_code == 200
    spec = (await client.get('/openapi.json')).json()
    assert spec['paths']['/api/v1/meta/filtros']['get']['security']


@pytest.mark.parametrize('cargo', ['diretoria', 'comercial', 'atendimento', 'perdas', 'operacao'])
async def test_all_demo_logins(client, cargo, infrastructure):
    response = await client.post(
        '/api/v1/auth/login', json={'login': cargo, 'senha': 'Demo-Venergy-2026!'}
    )
    assert response.status_code == 200
    payload = jwt.decode(
        response.json()['access_token'],
        infrastructure['settings'].jwt_secret.get_secret_value(),
        algorithms=['HS256'],
    )
    assert payload['cargo'] == cargo
    assert payload['exp'] - payload['iat'] == 8 * 3600


@pytest.mark.parametrize('login,senha', [('perdas', 'errada'), ('inexistente', 'errada')])
async def test_bad_credentials(client, login, senha):
    response = await client.post('/api/v1/auth/login', json={'login': login, 'senha': senha})
    assert response.status_code == 401
    assert 'access_token' not in response.json()
    assert response.headers['WWW-Authenticate'] == 'Bearer'


@pytest.mark.parametrize('kind', ['missing', 'malformed', 'expired', 'signature', 'unknown'])
async def test_invalid_tokens(client, infrastructure, db, kind):
    now = datetime.now(UTC)
    user = await db.fetchval("SELECT id FROM operations.usuarios WHERE login='perdas'")
    payload = {'sub': str(user), 'cargo': 'perdas', 'iat': now, 'exp': now + timedelta(hours=1)}
    secret = infrastructure['settings'].jwt_secret.get_secret_value()
    if kind == 'expired':
        payload.update(iat=now - timedelta(hours=2), exp=now - timedelta(hours=1))
    if kind == 'signature':
        secret = 'outra-chave-aleatoria-para-teste-32'
    if kind == 'unknown':
        payload['sub'] = str(uuid4())
    token = jwt.encode(payload, secret, algorithm='HS256')
    headers = (
        {}
        if kind == 'missing'
        else {'Authorization': 'Bearer ' + ('invalid' if kind == 'malformed' else token)}
    )
    response = await client.get('/api/v1/meta/carga', headers=headers)
    assert response.status_code == 401
    assert response.json()['code'] == 'NAO_AUTENTICADO'


async def test_disabled_user(client, headers, db):
    await db.execute("UPDATE operations.usuarios SET ativo=false WHERE login='perdas'")
    assert (await client.get('/api/v1/meta/carga', headers=headers)).status_code == 401


async def test_validation_hides_password(client):
    response = await client.post(
        '/api/v1/auth/login', json={'senha': 'segredo-que-nao-deve-voltar'}
    )
    assert response.status_code == 422
    assert 'segredo-que-nao-deve-voltar' not in response.text
    assert 'X-Request-ID' in response.headers


async def test_hash_and_seed_idempotency(infrastructure, db):
    from app.seed import seed

    before = await db.fetch('SELECT * FROM operations.usuarios ORDER BY login')
    assert all(r['senha_hash'].startswith('$argon2id$') for r in before)
    await seed(infrastructure['settings'])
    assert before == await db.fetch('SELECT * FROM operations.usuarios ORDER BY login')


@pytest.mark.parametrize('dependency', ['postgres', 'redis'])
async def test_health_reports_unavailable_dependency(infrastructure, dependency):
    values = (
        {'redis_url': 'redis://localhost:1/0'}
        if dependency == 'redis'
        else {'database_url_portal': 'postgresql+asyncpg://portal:portal_dev@localhost:1/venergy'}
    )
    app = create_app(infrastructure['settings'].model_copy(update=values))
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            response = await client.get('/api/v1/health')
    assert response.status_code == 503
    assert response.json()['code'] == 'SERVICO_INDISPONIVEL'
    assert response.json()['detail'][dependency] == 'indisponivel'


async def test_request_log_and_untrusted_request_id(client, caplog):
    import logging
    from uuid import UUID

    with caplog.at_level(logging.INFO, logger='venergy.requests'):
        response = await client.get(
            '/api/v1/meta/carga', headers={'X-Request-ID': 'id com espacos e dados invalidos'}
        )
    request_id = response.headers['X-Request-ID']
    UUID(request_id)
    assert response.status_code == 401
    assert f'request_id={request_id}' in caplog.text
