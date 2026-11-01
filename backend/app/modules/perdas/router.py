from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.auth import requer_cargo, usuario_atual
from app.core.database import session
from app.modules.perdas import repository, service
from app.modules.perdas.schemas import (
    Cancelamento,
    CriarOrdens,
    Despacho,
    Lote,
    Ordem,
    PaginaOrdens,
    Resultado,
    Status,
    Tentativa,
)

router = APIRouter(prefix='/ordens-inspecao', tags=['ordens'])
escrita = requer_cargo('perdas')


@router.get('', response_model=PaginaOrdens, dependencies=[Depends(usuario_atual)])
async def listar(
    status: Status | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(25, ge=1, le=100),
    db=Depends(session, scope='function'),
):
    return await repository.listar(db, status, page, size)


@router.post('', response_model=Lote, status_code=201)
async def criar(body: CriarOrdens, user=Depends(escrita), db=Depends(session, scope='function')):
    return await service.criar(db, body, user)


@router.post('/{id_}/despachar', response_model=Ordem)
async def despachar(
    id_: UUID, body: Despacho, user=Depends(escrita), db=Depends(session, scope='function')
):
    return await service.transicao(db, id_, 'despachar', body, user)


@router.post('/{id_}/tentativas', response_model=Ordem)
async def tentativa(
    id_: UUID, body: Tentativa, user=Depends(escrita), db=Depends(session, scope='function')
):
    return await service.transicao(db, id_, 'tentativas', body, user)


@router.post('/{id_}/resultado', response_model=Ordem)
async def resultado(
    id_: UUID, body: Resultado, user=Depends(escrita), db=Depends(session, scope='function')
):
    return await service.transicao(db, id_, 'resultado', body, user)


@router.post('/{id_}/cancelar', response_model=Ordem)
async def cancelar(
    id_: UUID, body: Cancelamento, user=Depends(escrita), db=Depends(session, scope='function')
):
    return await service.transicao(db, id_, 'cancelar', body, user)
