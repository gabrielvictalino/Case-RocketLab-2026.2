from app.core.errors import APIError
from app.core.periodos import validar_periodos
from app.modules.meta import repository
from app.modules.meta.schemas import Carga, Filtros


async def carga(db):
    data = await repository.carga_atual(db)
    if data is None:
        raise APIError(503, 'Nenhuma carga publicada; execute o importador', 'BASE_INDISPONIVEL')
    return Carga(**data)


async def filtros(db, periodo=None, comparacao=None):
    atual = await carga(db)
    if periodo is not None:
        validar_periodos(
            periodo, comparacao, atual.competencia_inicial, atual.competencia_mais_recente
        )
    elif comparacao is not None:
        raise APIError(422, 'Informe periodo junto com comparacao', 'PERIODO_INVALIDO')
    return Filtros(**await repository.dimensoes(db))
