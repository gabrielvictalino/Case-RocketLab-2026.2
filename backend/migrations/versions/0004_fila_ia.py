"""A fila da IA tira as UCs com ordem ativa, como a do portal."""

from alembic import op

revision = '0004'
down_revision = '0003'

# O SQL das três views é o de importador/views.sql. test_migrations confere que a view
# recriada aqui é igual à da carga, então quem muda uma das duas cópias muda a outra.
PORTAL_INSPECOES = """
    CREATE OR REPLACE VIEW portal_read.inspecoes AS
        SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
               kwh_recuperado,'historica'::text AS origem
        FROM analytics.inspecoes_historicas
        UNION ALL
        SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
               kwh_recuperado,'portal'::text AS origem
        FROM operations.inspecoes"""

AI_FILA = """
    CREATE OR REPLACE VIEW ai_read.fila_inspecao AS
        SELECT f.id_uc,f.score,f.motivos,f.energia_recuperar_kwh,f.energia_recuperar_reais
        FROM analytics.fila_inspecao f
        WHERE NOT EXISTS (
            SELECT 1 FROM operations.ordens_inspecao o
            WHERE o.id_uc = f.id_uc AND o.status IN ('ABERTA','EM_CAMPO'))"""

AI_INSPECOES = """
    CREATE OR REPLACE VIEW ai_read.inspecoes AS
        SELECT id_inspecao,id_uc,data,inspetor,resultado,
               CASE WHEN tipo IN ('BY-PASS','DESVIO DIRETO','LACRE VIOLADO',
                                  'LIGACAO CLANDESTINA','MEDIDOR ADULTERADO')
                    THEN tipo
                    WHEN tipo IS NOT NULL THEN 'OUTRO' END AS tipo_irregularidade,
               kwh_recuperado,origem
        FROM (
            SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
                   kwh_recuperado,'historica'::text AS origem
            FROM analytics.inspecoes_historicas
            UNION ALL
            SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
                   kwh_recuperado,'portal'::text AS origem
            FROM operations.inspecoes
        ) todas
        CROSS JOIN LATERAL (
            SELECT translate(upper(nullif(btrim(todas.tipo_irregularidade), '')),
                             'ÁÀÂÃÉÊÍÓÔÕÚÇáàâãéêíóôõúç',
                             'AAAAEEIOOOUCAAAAEEIOOOUC') AS tipo
        ) normal"""

# As views de antes desta migração, para o downgrade.
AI_FILA_ANTERIOR = """
    CREATE OR REPLACE VIEW ai_read.fila_inspecao AS
        SELECT id_uc,score,motivos,energia_recuperar_kwh,energia_recuperar_reais
        FROM analytics.fila_inspecao"""

AI_INSPECOES_ANTERIOR = """
    CREATE OR REPLACE VIEW ai_read.inspecoes AS
        SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
               kwh_recuperado,'historica'::text AS origem
        FROM analytics.inspecoes_historicas
        UNION ALL
        SELECT id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
               kwh_recuperado,'portal'::text AS origem
        FROM operations.inspecoes"""


def _se_existe(view: str, sql: str) -> str:
    # Sem carga, a view ainda não existe e a próxima importação a cria com o views.sql.
    return f"IF to_regclass('{view}') IS NOT NULL THEN {sql}; END IF;"


def upgrade():
    # Só as colunas da regra de ordem ativa: a view não expõe a ordem, e o importador
    # continua sem ler o resto (inspetor, motivo do cancelamento, autores).
    op.execute('GRANT SELECT (id_uc, status) ON operations.ordens_inspecao TO importador')
    # Num banco em que a 0002 rodou depois de uma carga, a view do portal lê
    # ai_read.inspecoes. Ela passa a ler as tabelas antes de a view da IA mudar, para o
    # portal continuar mostrando o texto do operador, e não o tipo fechado da IA.
    # Num banco já carregado, as views novas valem agora, e não só na próxima importação.
    op.execute(
        'DO $$ BEGIN '
        + _se_existe('portal_read.inspecoes', PORTAL_INSPECOES)
        + _se_existe('ai_read.fila_inspecao', AI_FILA)
        + _se_existe('ai_read.inspecoes', AI_INSPECOES)
        + ' END $$'
    )


def downgrade():
    # Volta as views da IA às da carga antes de tirar o grant: sem isso, o DROP das ordens
    # na 0001 esbarraria na dependência, e a IA perderia a fila até a próxima carga. A do
    # portal continua lendo as tabelas, como a carga a recria.
    op.execute(
        'DO $$ BEGIN '
        + _se_existe('ai_read.fila_inspecao', AI_FILA_ANTERIOR)
        + _se_existe('ai_read.inspecoes', AI_INSPECOES_ANTERIOR)
        + ' END $$'
    )
    op.execute('REVOKE SELECT (id_uc, status) ON operations.ordens_inspecao FROM importador')
