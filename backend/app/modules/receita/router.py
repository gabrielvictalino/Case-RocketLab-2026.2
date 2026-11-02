from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.auth import usuario_atual
from app.core.database import session
from app.core.metricas import Recorte
from app.modules.receita import service
from app.modules.receita.schemas import Decomposicao

router = APIRouter(prefix='/receita', tags=['receita'], dependencies=[Depends(usuario_atual)])


@router.get('/decomposicao', response_model=Decomposicao)
async def decomposicao(
    periodo: str,
    recorte: Annotated[Recorte, Query()],
    comparacao: str | None = None,
    db=Depends(session, scope='function'),
):
    return await service.decomposicao(db, periodo, comparacao, recorte)
