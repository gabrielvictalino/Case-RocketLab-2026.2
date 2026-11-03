from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.auth import bearer, usuario_atual
from app.core.database import session
from app.modules.assistente import service
from app.modules.assistente.schemas import Auditoria, Conversa, Pergunta, RespostaPergunta

router = APIRouter(prefix='/assistente', tags=['assistente'])


async def usuario_da_pergunta(
    request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer)
):
    # A sessão de `usuario_atual` duraria a rota inteira, inclusive a espera pelo modelo.
    # Aqui ela fecha logo depois de conferir o token.
    async with request.app.state.portal_sessions() as db, db.begin():
        return await usuario_atual(request, credentials, db)


@router.post('/perguntas', response_model=RespostaPergunta)
async def perguntar(body: Pergunta, request: Request, user=Depends(usuario_da_pergunta)):
    return await service.perguntar(request.app.state, body, user)


@router.get('/conversas/{conversa_id}', response_model=Conversa)
async def conversa(
    conversa_id: UUID, user=Depends(usuario_atual), db=Depends(session, scope='function')
):
    return await service.conversa(db, conversa_id, user)


@router.get('/respostas/{id_resposta}/auditoria', response_model=Auditoria)
async def auditoria(
    id_resposta: UUID, user=Depends(usuario_atual), db=Depends(session, scope='function')
):
    return await service.auditoria(db, id_resposta, user)
