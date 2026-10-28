from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy import text

from app.core.database import session
from app.core.errors import APIError

password_hash = PasswordHash.recommended()
bearer = HTTPBearer(auto_error=False)
DUMMY_HASH = password_hash.hash('credencial-inexistente-para-tempo-constante')


def emitir_token(usuario, settings):
    now = datetime.now(UTC)
    return jwt.encode(
        {
            'sub': str(usuario['id']),
            'cargo': usuario['cargo'],
            'iat': now,
            'exp': now + timedelta(hours=settings.jwt_expiration_hours),
        },
        settings.jwt_secret.get_secret_value(),
        algorithm='HS256',
    )


async def usuario_atual(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(session, scope='function'),
):
    try:
        if credentials is None:
            raise ValueError()
        payload = jwt.decode(
            credentials.credentials,
            request.app.state.settings.jwt_secret.get_secret_value(),
            algorithms=['HS256'],
            options={'require': ['sub', 'cargo', 'exp', 'iat']},
        )
        user_id = UUID(payload['sub'])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise APIError(401, 'Token ausente, inválido ou expirado', 'NAO_AUTENTICADO') from None
    user = (
        (
            await db.execute(
                text(
                    'SELECT id, login, nome, cargo FROM operations.usuarios WHERE id=:id AND ativo'
                ),
                {'id': user_id},
            )
        )
        .mappings()
        .first()
    )
    if user is None or user['cargo'] != payload['cargo']:
        raise APIError(401, 'Usuário inativo ou token desatualizado', 'NAO_AUTENTICADO')
    return user


def requer_cargo(*cargos):
    async def check(user=Depends(usuario_atual)):
        if user['cargo'] not in cargos:
            raise APIError(403, 'Cargo sem permissão para esta ação', 'SEM_PERMISSAO')
        return user

    return check
