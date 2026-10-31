import pytest

from venergy_ai.guarda_sql import SQLRejeitado, validar_sql

VIEWS = {'ucs', 'inspecoes', 'receita_volume_mensal', 'continuidade_alimentador_mensal'}


def rejeita(sql, trecho):
    with pytest.raises(SQLRejeitado) as erro:
        validar_sql(sql, VIEWS)
    assert trecho in str(erro.value)


@pytest.mark.parametrize(
    'sql,esperado',
    [
        (
            'SELECT * FROM ai_read.ucs',
            'SELECT * FROM ai_read.ucs LIMIT 1000',
        ),
        (
            'select municipio, count(*) from UCS group by 1',
            'SELECT municipio, COUNT(*) FROM ai_read.ucs GROUP BY 1 LIMIT 1000',
        ),
        (
            'WITH m AS (SELECT alimentador, avg(dec) AS dec '
            'FROM continuidade_alimentador_mensal GROUP BY 1) '
            'SELECT * FROM m ORDER BY dec DESC LIMIT 10',
            'WITH m AS (SELECT alimentador, AVG(dec) AS dec '
            'FROM ai_read.continuidade_alimentador_mensal GROUP BY 1) '
            'SELECT * FROM m ORDER BY dec DESC LIMIT 10',
        ),
        (
            'SELECT id_uc, lag(valor) OVER (PARTITION BY id_uc ORDER BY competencia) '
            'FROM ai_read.receita_volume_mensal',
            'SELECT id_uc, LAG(valor) OVER (PARTITION BY id_uc ORDER BY competencia) '
            'FROM ai_read.receita_volume_mensal LIMIT 1000',
        ),
        (
            'SELECT * FROM ai_read.ucs WHERE id_uc IN '
            '(SELECT id_uc FROM ai_read.inspecoes) LIMIT 5000 OFFSET 20',
            'SELECT * FROM ai_read.ucs WHERE id_uc IN '
            '(SELECT id_uc FROM ai_read.inspecoes) LIMIT 1000 OFFSET 20',
        ),
        (
            'SELECT id_uc FROM ai_read.ucs UNION SELECT id_uc FROM ai_read.inspecoes',
            'SELECT id_uc FROM ai_read.ucs UNION SELECT id_uc FROM ai_read.inspecoes LIMIT 1000',
        ),
        (
            'SELECT age(max(data_inspecao)) FROM ai_read.inspecoes '
            "WHERE motivo = 'x; DROP TABLE y'",
            'SELECT AGE(MAX(data_inspecao)) FROM ai_read.inspecoes '
            "WHERE motivo = 'x; DROP TABLE y' LIMIT 1000",
        ),
        (
            'SELECT * FROM ai_read.ucs -- ; DROP TABLE ai_read.ucs',
            'SELECT * FROM ai_read.ucs LIMIT 1000',
        ),
        (
            'SELECT * FROM ai_read.ucs /* ; DELETE FROM ai_read.ucs */ LIMIT 5;',
            'SELECT * FROM ai_read.ucs LIMIT 5',
        ),
    ],
)
def test_aceita_consultas_de_leitura(sql, esperado):
    assert validar_sql(sql, VIEWS) == esperado
    assert validar_sql(esperado, VIEWS) == esperado


@pytest.mark.parametrize(
    'sql',
    [
        "INSERT INTO ai_read.ucs (id_uc) VALUES ('x')",
        "UPDATE ai_read.ucs SET status = 'x'",
        'DELETE FROM ai_read.ucs',
        'MERGE INTO ai_read.ucs u USING ai_read.inspecoes i ON u.id_uc = i.id_uc '
        'WHEN MATCHED THEN DELETE',
        'DROP TABLE ai_read.ucs',
        'TRUNCATE ai_read.ucs',
        'ALTER TABLE ai_read.ucs ADD COLUMN x int',
        'CREATE TABLE copia AS SELECT * FROM ai_read.ucs',
        'GRANT SELECT ON ai_read.ucs TO PUBLIC',
        'COPY ai_read.ucs TO STDOUT',
        'SET statement_timeout = 0',
        'BEGIN',
        'EXPLAIN ANALYZE DELETE FROM ai_read.ucs',
        'DO $$ BEGIN DELETE FROM ai_read.ucs; END $$',
        'CALL limpar()',
        'VALUES (1)',
    ],
)
def test_rejeita_instrucao_que_nao_e_select(sql):
    rejeita(sql, 'Só é permitido SELECT')


@pytest.mark.parametrize(
    'sql,trecho',
    [
        ('WITH d AS (DELETE FROM ai_read.ucs RETURNING *) SELECT * FROM d', 'DELETE'),
        (
            "WITH n AS (INSERT INTO ai_read.ucs (id_uc) VALUES ('x') RETURNING *) SELECT * FROM n",
            'INSERT',
        ),
        (
            'SELECT * FROM ai_read.ucs WHERE id_uc IN (WITH u AS (UPDATE ai_read.ucs '
            "SET status = 'x' RETURNING id_uc) SELECT id_uc FROM u)",
            'UPDATE',
        ),
        ('SELECT * INTO copia FROM ai_read.ucs', 'SELECT INTO'),
        ('SELECT * FROM ai_read.ucs FOR UPDATE', 'FOR UPDATE'),
    ],
)
def test_rejeita_escrita_dentro_do_select(sql, trecho):
    rejeita(sql, trecho)


@pytest.mark.parametrize(
    'sql',
    [
        'SELECT 1; SELECT 2',
        'SELECT * FROM ai_read.ucs; DROP TABLE ai_read.ucs',
        'SELECT * FROM ai_read.ucs; COMMIT; DROP TABLE ai_read.ucs',
    ],
)
def test_rejeita_multiplas_instrucoes(sql):
    rejeita(sql, 'exatamente uma instrução')


@pytest.mark.parametrize(
    'sql',
    [
        # Comentário de linha que termina antes do ponto e vírgula.
        'SELECT * FROM ai_read.ucs --\n; DELETE FROM ai_read.ucs',
        'SELECT * FROM ai_read.ucs /* fim */; DELETE FROM ai_read.ucs',
        # Comentários aninhados fecham onde o Postgres fecha.
        'SELECT 1 /* a /* b */ */; DROP TABLE ai_read.ucs',
        # Sem E'', a barra não escapa a aspa, e o DROP fica fora da string.
        "SELECT 'a\\'; DROP TABLE ai_read.ucs; --'",
    ],
)
def test_rejeita_comentario_ou_string_escondendo_instrucao(sql):
    rejeita(sql, 'exatamente uma instrução')


@pytest.mark.parametrize(
    'sql,funcao',
    [
        ('SELECT pg_sleep(10)', 'pg_sleep'),
        ("SELECT pg_sleep_for('5 minutes')", 'pg_sleep_for'),
        ('SELECT PG_SLEEP(1) FROM ai_read.ucs', 'PG_SLEEP'),
        ('SELECT "pg_sleep"(1)', 'pg_sleep'),
        ("SELECT * FROM pg_read_file('/etc/passwd')", 'pg_read_file'),
        ("SELECT * FROM dblink('host=x', 'DELETE FROM t') AS t(a int)", 'dblink'),
        ("SELECT lo_import('/etc/passwd')", 'lo_import'),
        ("SELECT lo_export(1, '/tmp/x')", 'lo_export'),
        ("SELECT set_config('statement_timeout', '0', false)", 'set_config'),
        ("SELECT current_setting('search_path')", 'current_setting'),
        (
            "SELECT query_to_xml('SELECT * FROM operations.usuarios', true, true, '')",
            'query_to_xml',
        ),
        ("SELECT nextval('operations.ordens_inspecao_id_seq')", 'nextval'),
        ('SELECT pg_terminate_backend(1)', 'pg_terminate_backend'),
        ('SELECT * FROM ai_read.ucs WHERE id_uc = (SELECT pg_sleep(1)::text)', 'pg_sleep'),
        ('WITH x AS (SELECT pg_sleep(1)) SELECT * FROM x', 'pg_sleep'),
        ("SELECT * FROM ai_read.ucs u, LATERAL pg_ls_dir('.') d", 'pg_ls_dir'),
    ],
)
def test_rejeita_funcao_proibida(sql, funcao):
    rejeita(sql, f'Função não permitida: {funcao}')


@pytest.mark.parametrize(
    'sql',
    [
        'SELECT pg_catalog.pg_sleep(1)',
        "SELECT pg_catalog.current_setting('search_path')",
        'SELECT ai_read.age(now())',
    ],
)
def test_rejeita_funcao_com_schema(sql):
    rejeita(sql, 'Função com schema')


@pytest.mark.parametrize(
    'sql',
    [
        'SELECT * FROM operations.usuarios',
        'SELECT * FROM analytics.dim_uc',
        'SELECT * FROM portal_read.inspecoes',
        'SELECT * FROM pg_catalog.pg_user',
        'SELECT * FROM information_schema.tables',
        'SELECT * FROM pg_class',
        'SELECT * FROM usuarios',
        'SELECT * FROM venergy.ai_read.ucs',
        'SELECT * FROM "AI_READ".ucs',
        'SELECT * FROM ai_read."UCS"',
        'SELECT * FROM ai_read.ucs WHERE id_uc IN (SELECT id_uc FROM operations.inspecoes)',
        'WITH u AS (SELECT * FROM operations.usuarios) SELECT * FROM u',
        'SELECT * FROM ai_read.ucs u JOIN analytics.dim_uc d ON u.id_uc = d.id_uc',
        # A CTE "usuarios" não vale fora da subconsulta que a define.
        'SELECT * FROM (WITH usuarios AS (SELECT 1) SELECT 1) s, usuarios',
    ],
)
def test_rejeita_tabela_fora_da_allowlist(sql):
    rejeita(sql, 'Tabela fora do catálogo')


@pytest.mark.parametrize(
    'sql',
    [
        "SELECT 'operations.usuarios'::regclass",
        "SELECT CAST('pg_authid' AS regclass)",
        "SELECT 'ai_read'::regnamespace",
        "SELECT 'x'::pg_catalog.regclass",
        'SELECT 16384::oid',
    ],
)
def test_rejeita_conversao_para_tipo_do_catalogo(sql):
    rejeita(sql, 'Conversão para tipo do catálogo')


@pytest.mark.parametrize('sql', ['', '   ', '-- só comentário', 'SELECT FROM WHERE', 'SELEC 1'])
def test_rejeita_sql_vazio_ou_invalido(sql):
    with pytest.raises(SQLRejeitado):
        validar_sql(sql, VIEWS)


def test_motivo_cita_as_views_para_a_nova_tentativa():
    rejeita(
        'SELECT * FROM operations.usuarios',
        'Use só as views de ai_read: continuidade_alimentador_mensal, inspecoes, '
        'receita_volume_mensal, ucs.',
    )


@pytest.mark.parametrize(
    'limite,esperado',
    [
        ('', 'LIMIT 1000'),
        ('LIMIT 10', 'LIMIT 10'),
        ('LIMIT 0', 'LIMIT 0'),
        ('LIMIT 1000', 'LIMIT 1000'),
        ('LIMIT 1001', 'LIMIT 1000'),
        ('LIMIT ALL', 'LIMIT 1000'),
        ('LIMIT NULL', 'LIMIT 1000'),
        ('LIMIT 5 + 5', 'LIMIT 10'),
        ("LIMIT '5'", 'LIMIT 5'),
        ('LIMIT 5000 OFFSET 20', 'LIMIT 1000 OFFSET 20'),
        ('FETCH FIRST 5 ROWS ONLY', 'LIMIT 5'),
        ('FETCH FIRST ROW ONLY', 'LIMIT 1'),
        ('FETCH FIRST 5000 ROWS ONLY', 'LIMIT 1000'),
        ('OFFSET 5 ROWS FETCH NEXT 3 ROWS ONLY', 'LIMIT 3 OFFSET 5'),
    ],
)
def test_mantem_o_limite_pedido_ate_o_maximo(limite, esperado):
    sql = validar_sql(f'SELECT * FROM ai_read.ucs ORDER BY dec DESC {limite}', VIEWS)
    assert sql == f'SELECT * FROM ai_read.ucs ORDER BY dec DESC {esperado}'


@pytest.mark.parametrize(
    'limite,trecho',
    [
        ('FETCH FIRST 5 ROWS WITH TIES', 'WITH TIES'),
        ('FETCH FIRST 5 PERCENT ROWS ONLY', 'PERCENT'),
        ('LIMIT -1', 'inteiro não negativo'),
        ('LIMIT 2.5', 'inteiro não negativo'),
        ('LIMIT 10 / 3', 'inteiro não negativo'),
        ('LIMIT (SELECT count(*) FROM ai_read.ucs)', 'inteiro não negativo'),
    ],
)
def test_rejeita_limite_que_nao_e_inteiro(limite, trecho):
    rejeita(f'SELECT * FROM ai_read.ucs ORDER BY dec DESC {limite}', trecho)
