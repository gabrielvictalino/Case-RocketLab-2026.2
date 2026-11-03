"""Auditoria das perguntas ao agente, gravada pela role do portal."""

from alembic import op

revision = '0004'
down_revision = '0003'


def upgrade():
    op.execute("""CREATE TABLE operations.agente_auditoria (
        id uuid PRIMARY KEY,
        conversa_id uuid NOT NULL,
        usuario_id uuid NOT NULL REFERENCES operations.usuarios,
        pergunta text NOT NULL,
        contexto jsonb NOT NULL,
        consultas jsonb NOT NULL DEFAULT '[]',
        sql_gerado text,
        sql_executado text,
        numero_linhas integer CHECK (numero_linhas >= 0),
        resposta text,
        nao_sei boolean NOT NULL DEFAULT false,
        motivo text,
        modelo text,
        tokens_entrada integer CHECK (tokens_entrada >= 0),
        tokens_saida integer CHECK (tokens_saida >= 0),
        latencia_ms integer NOT NULL CHECK (latencia_ms >= 0),
        erro text,
        criado_em timestamptz NOT NULL DEFAULT now(),
        CHECK (resposta IS NOT NULL OR erro IS NOT NULL),
        CHECK (NOT nao_sei OR motivo IS NOT NULL)
    )""")
    op.execute(
        'CREATE INDEX ix_agente_auditoria_conversa '
        'ON operations.agente_auditoria(conversa_id, criado_em)'
    )
    # Só o portal grava e lê: a role ai_read não tem USAGE em operations.
    op.execute('GRANT SELECT, INSERT ON operations.agente_auditoria TO portal')


def downgrade():
    op.execute('DROP TABLE operations.agente_auditoria')
