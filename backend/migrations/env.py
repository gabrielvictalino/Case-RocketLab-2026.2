import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings


def configure(connection):
    context.configure(
        connection=connection,
        target_metadata=None,
        include_schemas=True,
        include_name=lambda name, type_, parent: type_ != 'schema' or name == 'operations',
        version_table_schema='operations',
    )
    with context.begin_transaction():
        context.run_migrations()


async def run():
    engine = create_async_engine(Settings().database_url_migrations, poolclass=pool.NullPool)
    async with engine.connect() as connection:
        await connection.run_sync(configure)
    await engine.dispose()


asyncio.run(run())
