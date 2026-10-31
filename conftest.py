"""Integração real: não substitui PostgreSQL por SQLite nem silencia falhas do Docker."""

import asyncio
import io
import os
import subprocess
import sys
import tarfile
from pathlib import Path

import asyncpg
import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

from app.core.config import Settings
from app.main import create_app
from app.seed import seed
from importador.loader import load

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / 'contracts/samples'


@pytest.fixture(scope='session')
def infrastructure():
    with (
        PostgresContainer('postgres:17', driver='psycopg') as pg,
        RedisContainer('redis:7-alpine') as redis,
    ):
        # Executa o mesmo bootstrap do Compose usando psql e valores de teste.
        buffer = io.BytesIO()
        payload = (ROOT / 'infra/postgres/init.sql').read_bytes()
        with tarfile.open(fileobj=buffer, mode='w') as archive:
            entry = tarfile.TarInfo('init.sql')
            entry.size = len(payload)
            archive.addfile(entry, io.BytesIO(payload))
        pg.get_wrapped_container().put_archive('/tmp', buffer.getvalue())
        result = pg.exec(
            [
                'psql',
                '-U',
                pg.username,
                '-d',
                pg.dbname,
                '-v',
                'ON_ERROR_STOP=1',
                '-v',
                'portal_password=portal_dev',
                '-v',
                'ai_password=ai_dev',
                '-v',
                'importador_password=importador_dev',
                '-f',
                '/tmp/init.sql',
            ]
        )
        assert result.exit_code == 0, result.output.decode()
        host, port = pg.get_container_host_ip(), pg.get_exposed_port(5432)
        base = f'{host}:{port}/{pg.dbname}'
        admin_url = f'postgresql://{pg.username}:{pg.password}@{base}'
        settings = Settings(
            database_url_portal=f'postgresql+asyncpg://portal:portal_dev@{base}',
            database_url_ai=f'postgresql+asyncpg://ai_read:ai_dev@{base}',
            database_url_migrations=admin_url.replace('postgresql://', 'postgresql+asyncpg://'),
            redis_url=f'redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0',
        )
        subprocess.run(
            [sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', 'upgrade', 'head'],
            cwd=ROOT,
            check=True,
            env={**os.environ, 'DATABASE_URL_MIGRATIONS': settings.database_url_migrations},
        )
        importer_url = f'postgresql://importador:importador_dev@{base}'
        asyncio.run(seed(settings))
        asyncio.run(load(SAMPLES, importer_url, settings.redis_url))
        yield dict(settings=settings, admin_url=admin_url, importer_url=importer_url)


@pytest.fixture
async def db(infrastructure):
    connection = await asyncpg.connect(infrastructure['admin_url'])
    await connection.execute(
        'TRUNCATE operations.inspecoes, operations.ordem_eventos, operations.ordens_inspecao'
    )
    await connection.execute('UPDATE operations.usuarios SET ativo=true')
    yield connection
    await connection.close()


@pytest.fixture
async def client(infrastructure, db):
    app = create_app(infrastructure['settings'])
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as http:
            yield http


@pytest.fixture
async def headers(client):
    result = await client.post(
        '/api/v1/auth/login', json={'login': 'perdas', 'senha': 'Demo-Venergy-2026!'}
    )
    assert result.status_code == 200
    return {'Authorization': 'Bearer ' + result.json()['access_token']}
