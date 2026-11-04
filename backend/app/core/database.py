from fastapi import Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Mesmo número de `importador.loader.SWAP_LOCK`. O importador o pega exclusivo só na troca
# de `analytics` (renomeação, views e registro da carga, num commit só); cada leitura do
# portal o pega compartilhado até o fim da transação. Assim a carga lida em
# `operations.cargas` e os números de `portal_read` saem sempre da mesma publicação.
SWAP_LOCK = 7820361


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


async def sincronizar_com_a_publicacao(db):
    """Impede que uma carga seja publicada no meio da transação.

    O lock é de transação: o commit ou o rollback o soltam, e a conexão volta limpa ao
    pool. Uma publicação em curso faz a leitura esperar a troca terminar; as leituras que
    chegam depois de o importador pedir o lock entram na fila atrás dele."""
    await db.execute(text('SELECT pg_advisory_xact_lock_shared(:chave)'), {'chave': SWAP_LOCK})


async def session(request: Request):
    async with request.app.state.portal_sessions() as db, db.begin():
        await sincronizar_com_a_publicacao(db)
        yield db


async def ai_session(request: Request):
    async with request.app.state.ai_sessions() as db, db.begin():
        yield db
