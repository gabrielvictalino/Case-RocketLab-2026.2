from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.errors import APIError

# Mesmo número de `importador.loader.SWAP_LOCK`. O importador o pega exclusivo só na troca
# de `analytics` (renomeação, views e registro da carga, num commit só); cada leitura do
# portal o pega compartilhado até o fim da transação. Assim a carga lida em
# `operations.cargas` e os números de `portal_read` saem sempre da mesma publicação.
SWAP_LOCK = 7820361
# Teto de cada comando no asyncpg. Estourá-lo cancela o comando no cliente e vira 500.
COMMAND_TIMEOUT_S = 5
# Quanto uma leitura espera pela troca, medido pelo `lock_timeout` do servidor. Fica abaixo
# do COMMAND_TIMEOUT_S, para a espera expirar como erro do banco e virar 503, e acima do
# tempo que o importador pode segurar a fila (`importador.loader.ESPERA_DA_TROCA_MS`, uma
# vez na fila pelo lock e outra nos locks da própria troca).
ESPERA_DA_PUBLICACAO_MS = 4000
LOCK_NAO_DISPONIVEL = '55P03'


def create_engines(settings):
    # A sessão da IA é criada separadamente e nunca recebe a conexão do portal.
    return (
        create_async_engine(
            settings.database_url_portal,
            pool_pre_ping=True,
            connect_args={'timeout': 3, 'command_timeout': COMMAND_TIMEOUT_S},
        ),
        create_async_engine(
            settings.database_url_ai,
            pool_pre_ping=True,
            connect_args={'timeout': 3, 'command_timeout': COMMAND_TIMEOUT_S},
        ),
    )


async def sincronizar_com_a_publicacao(db):
    """Impede que uma carga seja publicada no meio da transação.

    O lock é de transação: o commit ou o rollback o soltam, e a conexão volta limpa ao
    pool. Uma publicação em curso faz a leitura esperar a troca terminar; as leituras que
    chegam depois de o importador pedir o lock entram na fila atrás dele. A espera tem
    prazo: se a troca não terminar a tempo, a resposta é 503 com `Retry-After`, e o
    `lock_timeout` volta ao padrão para o resto da transação."""
    await db.execute(text(f"SET LOCAL lock_timeout = '{ESPERA_DA_PUBLICACAO_MS}ms'"))
    try:
        await db.execute(text('SELECT pg_advisory_xact_lock_shared(:chave)'), {'chave': SWAP_LOCK})
    except DBAPIError as erro:
        if getattr(erro.orig, 'sqlstate', None) != LOCK_NAO_DISPONIVEL:
            raise
        raise APIError(
            503,
            'Uma carga está sendo publicada. Tente de novo em instantes.',
            'CARGA_EM_PUBLICACAO',
            {'Retry-After': '5'},
        ) from erro
    await db.execute(text('SET LOCAL lock_timeout = DEFAULT'))


async def session(request: Request):
    async with request.app.state.portal_sessions() as db, db.begin():
        await sincronizar_com_a_publicacao(db)
        yield db


async def ai_session(request: Request):
    async with request.app.state.ai_sessions() as db, db.begin():
        yield db
