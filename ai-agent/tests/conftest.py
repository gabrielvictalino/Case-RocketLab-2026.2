import asyncpg
import pytest


@pytest.fixture
async def ai(infrastructure):
    """Conexão como a role ai_read, a mesma que o executor do agente usa."""
    url = infrastructure['settings'].database_url_ai.replace(
        'postgresql+asyncpg://', 'postgresql://'
    )
    connection = await asyncpg.connect(url)
    yield connection
    await connection.close()
