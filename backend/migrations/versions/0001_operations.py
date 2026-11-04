from pathlib import Path

from alembic import op

revision = '0001'
down_revision = None


def upgrade():
    # cargas nasce no bootstrap; a partir desta revisão sua evolução é do Alembic.
    sql = (Path(__file__).parents[1] / 'sql/0001.sql').read_text()
    if op.get_context().as_sql:
        op.execute(sql)
    else:
        # asyncpg executa o script completo pelo protocolo simples, sem quebrar SQL
        # em ponto e vírgula dentro de comentários, strings ou funções.
        op.get_bind().connection.run_async(lambda connection: connection.execute(sql))


def downgrade():
    op.execute('DROP VIEW IF EXISTS ai_read.inspecoes')
    op.execute('DROP VIEW IF EXISTS portal_read.inspecoes')
    for table in ('inspecoes', 'ordem_eventos', 'ordens_inspecao', 'usuarios'):
        op.execute(f'DROP TABLE operations.{table}')
    # cargas é preservada: pertence ao bootstrap anterior ao Alembic.
