from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.core.auth import usuario_atual
from app.core.database import session
from app.modules.metricas import Recorte
from app.modules.receita import service
from app.modules.receita.schemas import Decomposicao, Grupos, Locais

router = APIRouter(prefix='/receita', tags=['receita'], dependencies=[Depends(usuario_atual)])


@router.get('/decomposicao', response_model=Decomposicao)
async def decomposicao(
    periodo: str,
    recorte: Annotated[Recorte, Query()],
    comparacao: str | None = None,
    db=Depends(session, scope='function'),
):
    return await service.decomposicao(db, periodo, comparacao, recorte)


@router.get('/locais', response_model=Locais)
async def locais(
    periodo: str,
    nivel: Literal['municipio', 'bairro'],
    recorte: Annotated[Recorte, Query()],
    comparacao: str | None = None,
    db=Depends(session, scope='function'),
):
    return await service.locais(db, periodo, comparacao, recorte, nivel)


@router.get('/grupos', response_model=Grupos)
async def grupos(
    periodo: str,
    recorte: Annotated[Recorte, Query()],
    comparacao: str | None = None,
    db=Depends(session, scope='function'),
):
    return await service.grupos(db, periodo, comparacao, recorte)
