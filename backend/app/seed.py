"""Seed explícito e idempotente, somente em desenvolvimento."""

import asyncio
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.auth import password_hash
from app.core.config import Settings

CARGOS = ('diretoria', 'comercial', 'atendimento', 'perdas', 'operacao')
SENHA_DEMO = 'Demo-Venergy-2026!'


async def seed(settings=None):
    settings = settings or Settings()
    if settings.app_env != 'development':
        raise RuntimeError('Seed de demonstração permitido somente em development')
    engine = create_async_engine(settings.database_url_portal)
    try:
        async with engine.begin() as db:
            for cargo in CARGOS:
                await db.execute(
                    text("""INSERT INTO operations.usuarios
                    (id,login,nome,cargo,senha_hash) VALUES (:id,:login,:nome,:cargo,:hash)
                    ON CONFLICT (login) DO NOTHING"""),
                    {
                        'id': uuid4(),
                        'login': cargo,
                        'nome': f'Demonstração {cargo}',
                        'cargo': cargo,
                        'hash': password_hash.hash(SENHA_DEMO),
                    },
                )
    finally:
        await engine.dispose()


if __name__ == '__main__':
    asyncio.run(seed())
