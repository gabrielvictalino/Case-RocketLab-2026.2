from fastapi import Request
from sqlalchemy.ext.asyncio import create_async_engine


def create_engines(settings):
    # A sessão da IA é criada separadamente e nunca recebe a conexão do portal.
    return (
        create_async_engine(
            settings.database_url_portal,
            pool_pre_ping=True,
            connect_args={'timeout': 3, 'command_timeout': 5},
        ),
        create_async_engine(
            settings.database_url_ai,
            pool_pre_ping=True,
            connect_args={'timeout': 3, 'command_timeout': 5},
        ),
    )


async def session(request: Request):
    async with request.app.state.portal_sessions() as db, db.begin():
        yield db


async def ai_session(request: Request):
    async with request.app.state.ai_sessions() as db, db.begin():
        yield db
