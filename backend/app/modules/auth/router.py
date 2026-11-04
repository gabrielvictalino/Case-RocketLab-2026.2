from fastapi import APIRouter, Depends, Request

from app.core.database import session
from app.modules.auth import service
from app.modules.auth.schemas import Login, Token

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/login', response_model=Token)
async def login(body: Login, request: Request, db=Depends(session, scope='function')):
    return await service.login(db, body, request.app.state.settings)
