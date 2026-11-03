"""A fila da IA tira as UCs com ordem ativa, como a do portal."""

from alembic import op

revision = '0004'
down_revision = '0003'


def upgrade():
    # Só as colunas da regra de ordem ativa: a view não expõe a ordem, e o importador
    # continua sem ler o resto (inspetor, motivo do cancelamento, autores).
    op.execute('GRANT SELECT (id_uc, status) ON operations.ordens_inspecao TO importador')
    # Num banco que já tem carga, as views novas valem agora, e não só na próxima
    # importação. O SQL é o de importador/views.sql.
    op.execute("""DO $$ BEGIN
        IF to_regclass('ai_read.fila_inspecao') IS NOT NULL THEN
            CREATE OR REPLACE VIEW ai_read.fila_inspecao AS
                SELECT f.id_uc,f.score,f.motivos,f.energia_recuperar_kwh,f.energia_recuperar_reais
                FROM analytics.fila_inspecao f
                WHERE NOT EXISTS (
                    SELECT 1 FROM operations.ordens_inspecao o
                    WHERE o.id_uc = f.id_uc AND o.status IN ('ABERTA','EM_CAMPO'));
        END IF;
        IF to_regclass('ai_read.inspecoes') IS NOT NULL THEN
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
                                     'ÁÀÂÃÉÊÍÓÔÕÚÇ', 'AAAAEEIOOOUC') AS tipo
                ) normal;
        END IF;
    END $$""")


def downgrade():
    # Volta a view à fila da carga antes de tirar o grant: sem isso, o DROP das ordens
    # na 0001 esbarraria na dependência, e a IA perderia a fila até a próxima carga.
    op.execute("""DO $$ BEGIN
        IF to_regclass('ai_read.fila_inspecao') IS NOT NULL THEN
            CREATE OR REPLACE VIEW ai_read.fila_inspecao AS
                SELECT id_uc,score,motivos,energia_recuperar_kwh,energia_recuperar_reais
                FROM analytics.fila_inspecao;
        END IF;
    END $$""")
    op.execute('REVOKE SELECT (id_uc, status) ON operations.ordens_inspecao FROM importador')
