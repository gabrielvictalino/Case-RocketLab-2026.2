from fastapi import APIRouter, Depends

from app.core.auth import usuario_atual
from app.core.database import session
from app.modules.meta import service
from app.modules.meta.schemas import Carga, Filtros

router = APIRouter(prefix='/meta', tags=['meta'], dependencies=[Depends(usuario_atual)])


@router.get('/carga', response_model=Carga)
async def carga(db=Depends(session, scope='function')):
    return await service.carga(db)


@router.get('/filtros', response_model=Filtros)
async def filtros(
    periodo: str | None = None, comparacao: str | None = None, db=Depends(session, scope='function')
):
    return await service.filtros(db, periodo, comparacao)
