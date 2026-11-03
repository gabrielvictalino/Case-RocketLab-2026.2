from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import usuario_atual
from app.core.database import session
from app.modules.ucs import service
from app.modules.ucs.schemas import VisaoUC

router = APIRouter(prefix='/ucs', tags=['ucs'], dependencies=[Depends(usuario_atual)])


@router.get('/{id_uc}', response_model=VisaoUC)
async def obter_visao_uc(
    id_uc: str,
    sem_evento_atipico: bool = False,
    db: AsyncSession = Depends(session, scope='function'),
):
    return await service.obter_visao_uc(db, id_uc, sem_evento_atipico)
