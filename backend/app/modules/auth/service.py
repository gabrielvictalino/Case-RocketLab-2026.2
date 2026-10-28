from app.core.auth import DUMMY_HASH, emitir_token, password_hash
from app.core.errors import APIError
from app.modules.auth import repository
from app.modules.auth.schemas import Token


async def login(db, body, settings):
    user = await repository.por_login(db, body.login)
    valid = password_hash.verify(
        body.senha.get_secret_value(), user['senha_hash'] if user else DUMMY_HASH
    )
    if not valid or user is None:
        raise APIError(401, 'Credenciais inválidas', 'CREDENCIAIS_INVALIDAS')
    return Token(
        access_token=emitir_token(user, settings), expires_in=settings.jwt_expiration_hours * 3600
    )
