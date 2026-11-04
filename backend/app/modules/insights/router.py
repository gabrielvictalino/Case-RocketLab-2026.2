from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.core.auth import usuario_em_sessao_curta
from app.modules.insights import service
from app.modules.insights.schemas import Insight, Tela
from app.modules.metricas import Recorte

router = APIRouter(prefix='/insights', tags=['insights'])


@router.get('/{tela}', response_model=Insight)
async def insight(
    tela: Tela,
    periodo: str,
    recorte: Annotated[Recorte, Query()],
    request: Request,
    comparacao: str | None = None,
    user=Depends(usuario_em_sessao_curta),
):
    return await service.insight(request.app.state, tela, periodo, comparacao, recorte, user)
