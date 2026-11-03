from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import usuario_atual
from app.core.database import session
from app.modules.continuidade import service
from app.modules.continuidade.schemas import Ordem, Ranking, RecorteContinuidade, Serie

router = APIRouter(
    prefix='/continuidade', tags=['continuidade'], dependencies=[Depends(usuario_atual)]
)


@router.get('/serie', response_model=Serie)
async def serie(
    periodo: str,
    recorte: Annotated[RecorteContinuidade, Query()],
    comparacao: str | None = None,
    sem_evento_atipico: bool = False,
    db=Depends(session, scope='function'),
):
    return await service.serie(db, periodo, comparacao, recorte, sem_evento_atipico)


@router.get('/ranking', response_model=Ranking)
async def ranking(
    periodo: str,
    recorte: Annotated[RecorteContinuidade, Query()],
    comparacao: str | None = None,
    sem_evento_atipico: bool = False,
    ordem: Ordem = 'chi',
    db=Depends(session, scope='function'),
):
    return await service.ranking(db, periodo, comparacao, recorte, sem_evento_atipico, ordem)
