import asyncpg
import pytest

pytestmark = pytest.mark.integration


async def test_ai_allowlist_and_no_write(infrastructure, db):
    url = infrastructure['settings'].database_url_ai.replace(
        'postgresql+asyncpg://', 'postgresql://'
    )
    ai = await asyncpg.connect(url)
    try:
        assert await ai.fetchval('SHOW default_transaction_read_only') == 'on'
        assert await ai.fetchval('SHOW statement_timeout') == '5s'
        assert await ai.fetchval('SELECT count(*) FROM ai_read.ucs') == 300
        assert await ai.fetchval('SELECT count(*) FROM ai_read.inspecoes') == 2
        assert not {'titular', 'documento_mascarado', 'endereco'} & set(
            (await ai.fetchrow('SELECT * FROM ai_read.ucs LIMIT 1')).keys()
        )
        for query in (
            'SELECT * FROM operations.usuarios',
            'SELECT * FROM analytics.dim_uc',
            'SELECT * FROM operations.cargas',
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ai.execute(query)
        with pytest.raises(asyncpg.ReadOnlySQLTransactionError):
            await ai.execute('CREATE TABLE ai_read.teste (id int)')
        # Mesmo desativando a conveniência de read-only, as ACLs continuam barrando escrita.
        await ai.execute('SET default_transaction_read_only=off')
        for query in (
            'CREATE TABLE ai_read.teste (id int)',
            'CREATE TABLE public.teste (id int)',
            'CREATE TEMP TABLE teste (id int)',
            "INSERT INTO ai_read.ucs(id_uc) VALUES ('UC999999')",
            'DELETE FROM operations.inspecoes',
            'SET ROLE portal',
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ai.execute(query)
    finally:
        await ai.close()


async def test_importer_cannot_write_operational_tables(infrastructure, db):
    connection = await asyncpg.connect(infrastructure['importer_url'])
    try:
        assert await connection.fetchval('SELECT count(*) FROM operations.inspecoes') == 0
        for table in ['usuarios', 'ordens_inspecao', 'ordem_eventos', 'inspecoes', 'cargas']:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(f'DELETE FROM operations.{table}')
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await connection.execute('UPDATE operations.inspecoes SET kwh_recuperado=0')
    finally:
        await connection.close()
