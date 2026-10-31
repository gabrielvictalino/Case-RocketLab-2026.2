import asyncpg
import pytest

from venergy_ai.guarda_sql import validar_sql

pytestmark = pytest.mark.integration

VIEWS = {'ucs', 'inspecoes'}


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


async def test_limite_imposto_vale_no_banco(ai):
    assert len(await ai.fetch(validar_sql('SELECT * FROM ucs', VIEWS))) == 300
    sql = validar_sql('SELECT * FROM ucs a CROSS JOIN ucs b', VIEWS)
    assert len(await ai.fetch(sql)) == 1000
