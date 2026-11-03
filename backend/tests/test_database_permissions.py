import asyncpg
import pytest
from importador.loader import PUBLICATION_LOCK

pytestmark = pytest.mark.integration

AI_VIEWS = {
    'atendimentos',
    'atendimentos_historico',
    'continuidade_alimentador_mensal',
    'fila_inspecao',
    'gd_uc',
    'inspecoes',
    'medidores_historico',
    'ocorrencias_uc',
    'receita_volume_mensal',
    'uc_consumo_faturamento_mensal',
    'ucs',
}
# Nomes da fonte e do contrato Gold para o titular, o documento, o endereço e o texto livre.
PERSONAL_COLUMNS = {
    'nome_titular',
    'titular',
    'cpf_cnpj',
    'documento_mascarado',
    'logradouro',
    'numero',
    'cep',
    'endereco',
    'descricao',
}


def ai_url(infrastructure):
    return infrastructure['settings'].database_url_ai.replace(
        'postgresql+asyncpg://', 'postgresql://'
    )


async def test_ai_views_are_reviewed_projections(infrastructure, db):
    relations = await db.fetch(
        """SELECT c.relname, c.relkind::text FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='ai_read'"""
    )
    assert {r['relname'] for r in relations} == AI_VIEWS
    assert {r['relkind'] for r in relations} == {'v'}
    columns = await db.fetch(
        """SELECT table_name, column_name FROM information_schema.columns
        WHERE table_schema='ai_read'"""
    )
    assert [
        (r['table_name'], r['column_name']) for r in columns if r['column_name'] in PERSONAL_COLUMNS
    ] == []
    # Grant view a view: nenhum privilégio padrão libera views futuras para a IA.
    assert not await db.fetchval("""SELECT EXISTS(
        SELECT 1 FROM pg_default_acl d, aclexplode(d.defaclacl) a
        WHERE a.grantee='ai_read'::regrole)""")
    ai = await asyncpg.connect(ai_url(infrastructure))
    try:
        # Fora as duas views com nome próprio, cada view projeta a tabela de mesmo nome.
        for view in AI_VIEWS - {'ucs', 'inspecoes'}:
            assert await ai.fetchval(f'SELECT count(*) FROM ai_read.{view}') == await db.fetchval(
                f'SELECT count(*) FROM analytics.{view}'
            )
    finally:
        await ai.close()


async def test_ai_cannot_read_other_schemas(infrastructure, db):
    relations = await db.fetch(
        """SELECT n.nspname, c.relname FROM pg_class c
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname IN ('analytics','operations','portal_read')
          AND c.relkind IN ('r','v','p')"""
    )
    assert {r['nspname'] for r in relations} == {'analytics', 'operations', 'portal_read'}
    ai = await asyncpg.connect(ai_url(infrastructure))
    try:
        for r in relations:
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ai.execute(f'SELECT 1 FROM {r["nspname"]}."{r["relname"]}" LIMIT 1')
    finally:
        await ai.close()


async def test_ai_cannot_call_session_file_or_remote_functions(infrastructure, db):
    ai = await asyncpg.connect(ai_url(infrastructure))
    try:
        for query in (
            "SELECT set_config('statement_timeout', '0', false)",
            'SELECT pg_sleep(0)',
            "SELECT pg_sleep_for('0 seconds')",
            'SELECT pg_sleep_until(now())',
            "SELECT pg_read_file('postgresql.conf')",
            "SELECT lo_import('/etc/hostname')",
            # O lock que serializa as cargas, nas variantes de sessão.
            f'SELECT pg_advisory_lock({PUBLICATION_LOCK})',
            f'SELECT pg_advisory_lock_shared({PUBLICATION_LOCK})',
            f'SELECT pg_try_advisory_lock({PUBLICATION_LOCK})',
            f'SELECT pg_try_advisory_lock_shared({PUBLICATION_LOCK})',
            'SELECT pg_advisory_lock(1, 2)',
            'SELECT pg_advisory_lock_shared(1, 2)',
            'SELECT pg_try_advisory_lock(1, 2)',
            'SELECT pg_try_advisory_lock_shared(1, 2)',
        ):
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await ai.execute(query)
        with pytest.raises(asyncpg.UndefinedFunctionError):
            await ai.execute("SELECT dblink_connect('dbname=postgres')")
    finally:
        await ai.close()
    assert not await db.fetchval(
        "SELECT EXISTS(SELECT 1 FROM pg_proc WHERE proname LIKE 'dblink%')"
    )
    # Portal e importador recebem as funções de volta.
    for url in (
        infrastructure['settings'].database_url_portal.replace(
            'postgresql+asyncpg://', 'postgresql://'
        ),
        infrastructure['importer_url'],
    ):
        connection = await asyncpg.connect(url)
        try:
            assert await connection.fetchval("SELECT set_config('application_name', 'x', false)")
            await connection.execute(
                "SELECT pg_sleep(0), pg_sleep_for('0 seconds'), pg_sleep_until(now())"
            )
        finally:
            await connection.close()


async def test_ai_allowlist_and_no_write(infrastructure, db):
    ai = await asyncpg.connect(ai_url(infrastructure))
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
            'SELECT * FROM portal_read.inspecoes',
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


async def test_default_grants_follow_republished_schema(infrastructure, db):
    from importador.loader import load
    from pathlib import Path

    await load(
        Path(__file__).resolve().parents[2] / 'contracts/samples', infrastructure['importer_url']
    )
    connection = await asyncpg.connect(infrastructure['importer_url'])
    try:
        await connection.execute('CREATE TABLE analytics.teste_grant (id integer)')
        assert await db.fetchval(
            "SELECT has_table_privilege('portal','analytics.teste_grant','SELECT')"
        )
    finally:
        await connection.execute('DROP TABLE IF EXISTS analytics.teste_grant')
        await connection.close()
