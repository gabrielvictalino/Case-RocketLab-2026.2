from pathlib import Path

from alembic import op

revision = '0001'
down_revision = None


def upgrade():
    # cargas nasce no bootstrap; a partir desta revisão sua evolução é do Alembic.
    sql = (Path(__file__).parents[1] / 'sql/0001.sql').read_text()
    for statement in sql.split(';'):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in ('inspecoes', 'ordem_eventos', 'ordens_inspecao', 'usuarios'):
        op.execute(f'DROP TABLE operations.{table}')
    # cargas é preservada: pertence ao bootstrap anterior ao Alembic.
