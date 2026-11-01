import asyncpg
import pytest

from venergy_ai.guarda_sql import FUNCOES_ANONIMAS_PERMITIDAS, LIMITE_MAXIMO, validar_sql

pytestmark = pytest.mark.integration

VIEWS = {'ucs', 'inspecoes'}

# Um exemplo para cada função da allowlist, que o sqlglot não conhece e regenera
# só pelo nome.
EXEMPLOS_DAS_FUNCOES_PERMITIDAS = {
    'age': "age(timestamp '2025-03-15', timestamp '2024-01-01')",
    'array_lower': 'array_lower(ARRAY[1, 2], 1)',
    'array_upper': 'array_upper(ARRAY[1, 2], 1)',
    'cardinality': 'cardinality(ARRAY[1, 2])',
    'clock_timestamp': 'clock_timestamp() IS NOT NULL',
    'every': '(SELECT every(x > 0) FROM generate_series(1, 3) AS g(x))',
    'gcd': 'gcd(12, 18)',
    'isfinite': "isfinite(date '2025-01-01')",
    'json_array_length': "json_array_length('[1, 2]'::json)",
    'json_build_array': 'json_build_array(1, 2)::text',
    'json_build_object': "json_build_object('a', 1)::text",
    'json_typeof': "json_typeof('1'::json)",
    'jsonb_agg': '(SELECT jsonb_agg(x)::text FROM generate_series(1, 3) AS g(x))',
    'jsonb_array_length': "jsonb_array_length('[1, 2]'::jsonb)",
    'jsonb_build_array': 'jsonb_build_array(1, 2)::text',
    'jsonb_build_object': "jsonb_build_object('a', 1)::text",
    'jsonb_extract_path_text': "jsonb_extract_path_text('{\"a\": 1}'::jsonb, 'a')",
    'jsonb_typeof': "jsonb_typeof('1'::jsonb)",
    'lcm': 'lcm(4, 6)',
    'make_date': 'make_date(2025, 3, 15)',
    'num_nonnulls': 'num_nonnulls(1, NULL)',
    'num_nulls': 'num_nulls(1, NULL)',
    'octet_length': "octet_length('abc')",
    'regexp_match': "regexp_match('abc', 'b')",
    'regexp_matches': "regexp_matches('abc', 'b')",
    'regexp_split_to_array': "regexp_split_to_array('a,b', ',')",
    'scale': 'scale(1.234)',
    'statement_timestamp': 'statement_timestamp() IS NOT NULL',
    'timezone': "timezone('UTC', timestamptz '2025-01-01 00:00:00+00')",
    'to_json': "to_json('a'::text)::text",
    'to_jsonb': "to_jsonb('a'::text)::text",
    'transaction_timestamp': 'transaction_timestamp() IS NOT NULL',
    'trim_scale': 'trim_scale(1.2300)',
}

# Construções que o sqlglot reescreve ao regenerar o SQL, ou comuns nas perguntas.
CONSULTAS_REESCRITAS = [
    'SELECT to_hex(255)',
    "SELECT date_part('year', date '2025-03-15')",
    'SELECT 2 = ALL(ARRAY[1, 2]), 2 = SOME(ARRAY[1, 2]), 2 = ANY(ARRAY[1, 2])',
    "SELECT to_char(date '2025-03-15', 'YYYY-MM'), to_char(1234.5, 'FM9999.00')",
    "SELECT to_char(timestamp '2025-03-15 10:05', 'DD/MM/YYYY HH24:MI')",
    "SELECT to_date('15/03/2025', 'DD/MM/YYYY'), extract(epoch from interval '1 hour')",
    "SELECT (date '2025-03-15' - interval '12 months')::date, make_interval(days => 3)",
    "SELECT date_bin(interval '15 minutes', timestamp '2025-01-01 10:07', timestamp '2025-01-01')",
    "SELECT substring('abcdef' from 2 for 3), position('c' in 'abcdef'), trim(both 'x' from 'xax')",
    "SELECT regexp_replace('abcb', 'b', 'x', 'g'), 'abc' ~* 'B', 'abc' SIMILAR TO 'a%'",
    "SELECT '{\"a\": 1}'::jsonb ->> 'a', 1 IS DISTINCT FROM 2",
    "SELECT (date '2025-01-01', date '2025-02-01') OVERLAPS (date '2025-01-15', date '2025-03-01')",
    'SELECT percentile_disc(0.9) WITHIN GROUP (ORDER BY x), mode() WITHIN GROUP (ORDER BY x % 2), '
    "string_agg(x::text, ',' ORDER BY x DESC) FROM generate_series(1, 5) AS g(x)",
    'SELECT x, sum(x) OVER (ORDER BY x ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), '
    'ntile(2) OVER (ORDER BY x) FROM generate_series(1, 5) AS g(x)',
    'SELECT x % 2 AS p, count(*) FROM generate_series(1, 5) AS g(x) '
    'GROUP BY ROLLUP (p) ORDER BY 1 NULLS LAST',
    'SELECT DISTINCT ON (x % 2) x FROM generate_series(1, 5) AS g(x) ORDER BY x % 2, x DESC',
    'SELECT a.x, b.y FROM generate_series(1, 3) AS a(x) '
    'CROSS JOIN LATERAL (SELECT a.x * 10 AS y) AS b ORDER BY 1',
    'WITH RECURSIVE r(n) AS (SELECT 1 UNION ALL SELECT n + 1 FROM r WHERE n < 5) '
    'SELECT sum(n) FROM r',
    'SELECT x FROM generate_series(1, 5) AS g(x) ORDER BY x OFFSET 1 ROWS FETCH NEXT 2 ROWS ONLY',
    "SELECT x FROM generate_series(1, 5) AS g(x) ORDER BY x LIMIT ' 2 '::int",
    'SELECT x FROM generate_series(1, 5) AS g(x) ORDER BY x LIMIT CAST(2 AS bigint)',
    '(SELECT x FROM generate_series(1, 5) AS g(x) ORDER BY x LIMIT 3) OFFSET 1',
    '(SELECT 1 AS x UNION SELECT 2) ORDER BY x DESC LIMIT 1',
]


@pytest.fixture
async def ai(infrastructure):
    url = infrastructure['settings'].database_url_ai.replace(
        'postgresql+asyncpg://', 'postgresql://'
    )
    connection = await asyncpg.connect(url)
    yield connection
    await connection.close()


# O texto executado é o regenerado pelo sqlglot; estes casos conferem que o Postgres
# aceita a forma regenerada das construções comuns nas perguntas do portal.
@pytest.mark.parametrize(
    'sql',
    [
        'SELECT municipio, classe, count(*) FILTER (WHERE flag_gd) AS com_gd '
        'FROM ucs GROUP BY 1, 2 ORDER BY 3 DESC',
        "SELECT date_trunc('month', data) AS mes, round(avg(kwh_recuperado)::numeric, 2) "
        'FROM inspecoes GROUP BY 1',
        'SELECT alimentador, rank() OVER (ORDER BY count(*) DESC) FROM ai_read.ucs '
        'GROUP BY alimentador',
        'SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY kwh_recuperado), '
        'max(age(data::timestamp)) FROM inspecoes',
        "WITH m AS (SELECT generate_series(date '2025-08-01', date '2025-12-01', "
        "interval '1 month') AS mes) SELECT m.mes, count(i.id_inspecao) FROM m "
        "LEFT JOIN inspecoes i ON date_trunc('month', i.data) = m.mes GROUP BY 1",
        'SELECT u.bairro, i.resultado FROM ucs u JOIN inspecoes i USING (id_uc) '
        "WHERE i.data >= date '2025-08-01' - interval '12 months' "
        "AND i.resultado ILIKE '%irregular%' LIMIT 20",
    ],
)
async def test_sql_regenerado_roda_como_ai_read(ai, sql):
    await ai.fetch(validar_sql(sql, VIEWS))


def test_toda_funcao_permitida_tem_exemplo():
    assert set(EXEMPLOS_DAS_FUNCOES_PERMITIDAS) == FUNCOES_ANONIMAS_PERMITIDAS


@pytest.mark.parametrize(
    'sql',
    [
        *(f'SELECT {exemplo}' for exemplo in EXEMPLOS_DAS_FUNCOES_PERMITIDAS.values()),
        *CONSULTAS_REESCRITAS,
    ],
)
async def test_sql_regenerado_da_o_mesmo_resultado(ai, sql):
    esperado = [tuple(linha) for linha in await ai.fetch(sql)]
    assert [tuple(linha) for linha in await ai.fetch(validar_sql(sql, VIEWS))] == esperado


async def test_limite_vale_no_banco(ai):
    ucs = await ai.fetchval('SELECT count(*) FROM ai_read.ucs')
    linhas = await ai.fetch(validar_sql('SELECT * FROM ucs a CROSS JOIN ucs b', VIEWS))
    assert len(linhas) == min(ucs * ucs, LIMITE_MAXIMO)
    linhas = await ai.fetch(validar_sql('SELECT * FROM ucs FETCH FIRST 5 ROWS ONLY', VIEWS))
    assert len(linhas) == min(ucs, 5)
