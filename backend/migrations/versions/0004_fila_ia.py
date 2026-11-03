"""A fila da IA tira as UCs com ordem ativa, como a do portal."""

from alembic import op

revision = '0004'
down_revision = '0003'


def upgrade():
    # Só as colunas da regra de ordem ativa: a view não expõe a ordem, e o importador
    # continua sem ler o resto (inspetor, motivo do cancelamento, autores).
    op.execute('GRANT SELECT (id_uc, status) ON operations.ordens_inspecao TO importador')


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
