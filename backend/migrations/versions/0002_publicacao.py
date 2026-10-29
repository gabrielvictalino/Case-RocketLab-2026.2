"""Ordenação de publicações e separação das views do portal."""

from alembic import op

revision = '0002'
down_revision = '0001'


def upgrade():
    # Backfill determinístico para bancos que já receberam cargas na revisão 0001.
    op.execute('CREATE SEQUENCE operations.cargas_ordem_publicacao_seq')
    op.execute('ALTER TABLE operations.cargas ADD COLUMN ordem_publicacao bigint')
    op.execute("""WITH ordenadas AS (
        SELECT id,row_number() OVER (ORDER BY carregado_em,id) AS numero
        FROM operations.cargas
    ) UPDATE operations.cargas c SET ordem_publicacao=o.numero
      FROM ordenadas o WHERE c.id=o.id""")
    op.execute("""SELECT setval('operations.cargas_ordem_publicacao_seq',
        coalesce(max(ordem_publicacao),0)+1,false) FROM operations.cargas""")
    op.execute("""ALTER TABLE operations.cargas
        ALTER COLUMN ordem_publicacao SET NOT NULL,
        ALTER COLUMN ordem_publicacao SET DEFAULT
            nextval('operations.cargas_ordem_publicacao_seq'),
        ALTER COLUMN carregado_em SET DEFAULT clock_timestamp(),
        ADD CONSTRAINT uq_cargas_publicacao UNIQUE (ordem_publicacao)""")
    op.execute("""ALTER SEQUENCE operations.cargas_ordem_publicacao_seq
        OWNED BY operations.cargas.ordem_publicacao""")
    op.execute('GRANT USAGE ON SEQUENCE operations.cargas_ordem_publicacao_seq TO importador')
    op.execute('CREATE SCHEMA portal_read AUTHORIZATION importador')
    op.execute('GRANT USAGE ON SCHEMA portal_read TO portal')
    # Se já houve carga, preserva a view do portal até a próxima publicação.
    op.execute("""DO $$ BEGIN
        IF to_regclass('ai_read.inspecoes') IS NOT NULL THEN
            EXECUTE 'CREATE VIEW portal_read.inspecoes AS SELECT
                id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,
                kwh_recuperado,origem FROM ai_read.inspecoes';
            ALTER VIEW portal_read.inspecoes OWNER TO importador;
            GRANT SELECT ON portal_read.inspecoes TO portal;
        END IF;
    END $$""")


def downgrade():
    op.execute('DROP VIEW IF EXISTS portal_read.inspecoes')
    op.execute('DROP SCHEMA portal_read')
    op.execute('ALTER TABLE operations.cargas DROP COLUMN ordem_publicacao')
    op.execute('ALTER TABLE operations.cargas ALTER COLUMN carregado_em SET DEFAULT now()')
