"""Importações da planilha de campo: a prévia fica salva até a confirmação."""

from alembic import op

revision = '0005'
down_revision = '0004'


def upgrade():
    op.execute("""CREATE TABLE operations.importacoes (
        id uuid PRIMARY KEY,
        arquivo text NOT NULL,
        autor uuid NOT NULL REFERENCES operations.usuarios,
        status text NOT NULL DEFAULT 'PREVIA' CHECK (status IN ('PREVIA','CONFIRMADA')),
        validas jsonb NOT NULL,
        erros jsonb NOT NULL,
        avisos jsonb NOT NULL,
        atualizadas integer CHECK (atualizadas >= 0),
        rejeitadas jsonb,
        criado_em timestamptz NOT NULL DEFAULT now(),
        confirmado_em timestamptz,
        CHECK ((status = 'CONFIRMADA') = (confirmado_em IS NOT NULL)),
        CHECK ((status = 'CONFIRMADA') = (atualizadas IS NOT NULL))
    )""")
    op.execute(
        'CREATE INDEX ix_importacoes_confirmadas ON operations.importacoes(confirmado_em DESC) '
        "WHERE status = 'CONFIRMADA'"
    )
    op.execute('GRANT SELECT, INSERT, UPDATE ON operations.importacoes TO portal')


def downgrade():
    op.execute('DROP TABLE operations.importacoes')
