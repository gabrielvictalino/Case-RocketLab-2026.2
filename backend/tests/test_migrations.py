import asyncio
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import asyncpg
import pytest

from importador.loader import load

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[2]


async def test_upgrade_existing_publication_and_downgrade(infrastructure):
    # Banco isolado no container da suíte; as roles já existem no cluster.
    name = 'migration_' + uuid4().hex
    admin = await asyncpg.connect(infrastructure['admin_url'])
    await admin.execute(f'CREATE DATABASE {name}')
    admin_url = infrastructure['admin_url'].rsplit('/', 1)[0] + '/' + name
    importer_url = infrastructure['importer_url'].rsplit('/', 1)[0] + '/' + name
    db = await asyncpg.connect(admin_url)

    async def migrate(*args):
        await asyncio.to_thread(
            subprocess.run,
            [sys.executable, '-m', 'alembic', '-c', 'backend/alembic.ini', *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                'DATABASE_URL_MIGRATIONS': admin_url.replace(
                    'postgresql://', 'postgresql+asyncpg://'
                ),
            },
        )

    try:
        await db.execute(f"""CREATE SCHEMA analytics AUTHORIZATION importador;
            CREATE SCHEMA ai_read AUTHORIZATION importador;
            CREATE SCHEMA operations;
            GRANT CREATE ON DATABASE {name} TO importador;
            GRANT USAGE ON SCHEMA analytics,operations,ai_read TO portal;
            GRANT USAGE ON SCHEMA operations TO importador;
            GRANT USAGE ON SCHEMA ai_read TO ai_read;""")
        bootstrap = (ROOT / 'infra/postgres/init.sql').read_text()
        await db.execute(
            'CREATE TABLE operations.cargas'
            + bootstrap.split('CREATE TABLE operations.cargas', 1)[1]
        )
        await migrate('upgrade', '0001')
        # Estado que o PR original deixava, antes da nova migração.
        await db.execute("""CREATE TABLE analytics.inspecoes_historicas
            (LIKE operations.inspecoes);
            ALTER TABLE analytics.inspecoes_historicas OWNER TO importador;
            CREATE VIEW ai_read.inspecoes AS SELECT id_inspecao,id_uc,data,inspetor,
                resultado,tipo_irregularidade,kwh_recuperado,'historica'::text AS origem
                FROM analytics.inspecoes_historicas
                UNION ALL SELECT id_inspecao,id_uc,data,inspetor,resultado,
                tipo_irregularidade,kwh_recuperado,'portal'::text
                FROM operations.inspecoes;
            ALTER VIEW ai_read.inspecoes OWNER TO importador;""")
        await db.execute(
            """INSERT INTO operations.cargas
            (id,batch_id,versao_contrato,sintetica,periodo_inicio,periodo_fim,manifesto)
            VALUES ($1,'anterior','0.1.0-provisional',true,'2022-07-01','2026-06-01','{}')""",
            uuid4(),
        )
        await migrate('upgrade', 'head')
        assert await db.fetchval('SELECT ordem_publicacao FROM operations.cargas') == 1
        assert await db.fetchval('SELECT count(*) FROM portal_read.inspecoes') == 0
        await load(ROOT / 'contracts/samples', importer_url)
        assert await db.fetchval('SELECT max(ordem_publicacao) FROM operations.cargas') == 2
        assert await db.fetchval('SELECT count(*) FROM portal_read.inspecoes') == 2
        await migrate('downgrade', 'base')
        assert await db.fetchval("SELECT to_regclass('operations.inspecoes')") is None
        assert await db.fetchval('SELECT count(*) FROM operations.cargas') == 2
        await migrate('upgrade', 'head')
        await load(ROOT / 'contracts/samples', importer_url)
        assert await db.fetchval('SELECT count(*) FROM portal_read.inspecoes') == 2
    finally:
        await db.close()
        await admin.execute(f'DROP DATABASE {name}')
        await admin.close()
