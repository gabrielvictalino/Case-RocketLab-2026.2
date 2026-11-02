from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import usuario_atual
from app.core.database import session
from app.core.metricas import Recorte
from app.modules.kpis import service
from app.modules.kpis.schemas import KPIs, Serie

router = APIRouter(prefix='/kpis', tags=['kpis'], dependencies=[Depends(usuario_atual)])


@router.get('', response_model=KPIs)
async def kpis(
    periodo: str,
    recorte: Annotated[Recorte, Query()],
    comparacao: str | None = None,
    db=Depends(session, scope='function'),
):
    return await service.kpis(db, periodo, comparacao, recorte)


@router.get('/serie', response_model=Serie)
async def serie(
    periodo: str,
    recorte: Annotated[Recorte, Query()],
    comparacao: str | None = None,
    db=Depends(session, scope='function'),
):
    return await service.serie(db, periodo, comparacao, recorte)
