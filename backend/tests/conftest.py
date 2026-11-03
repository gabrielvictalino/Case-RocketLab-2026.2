import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
async def portal(infrastructure, db):
    """O app com o lifespan rodando: os testes trocam `app.state.assistente` pelo agente
    com o modelo simulado."""
    app = create_app(infrastructure['settings'])
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as http:
            yield app, http
