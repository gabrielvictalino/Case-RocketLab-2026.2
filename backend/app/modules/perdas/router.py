from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, UploadFile

from app.core.auth import requer_cargo, usuario_atual
from app.core.database import session
from app.modules.perdas import planilha, repository, service
from app.modules.perdas.schemas import (
    Cancelamento,
    CriarOrdens,
    Despacho,
    FiltroFila,
    ImportacaoConfirmada,
    Lote,
    Ordem,
    PaginaFila,
    PaginaOrdens,
    PreviaImportacao,
    Resultado,
    Status,
    Tentativa,
)

router = APIRouter(prefix='/ordens-inspecao', tags=['ordens'])
escrita = requer_cargo('perdas')
ARQUIVO_EXCEL = {
    200: {
        'content': {planilha.XLSX: {'schema': {'type': 'string', 'format': 'binary'}}},
        'description': 'Planilha Excel',
    }
}


def _excel(conteudo: bytes, nome: str) -> Response:
    cabecalhos = {'Content-Disposition': f'attachment; filename="{nome}"'}
    return Response(conteudo, media_type=planilha.XLSX, headers=cabecalhos)


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


@router.get(
    '/export',
    response_class=Response,
    responses=ARQUIVO_EXCEL,
    dependencies=[Depends(usuario_atual)],
)
async def exportar_ordens(db=Depends(session, scope='function')):
    return _excel(await service.exportar_ordens(db), 'planilha-de-campo.xlsx')


@router.post('/importacoes', response_model=PreviaImportacao, status_code=201)
async def importar(
    arquivo: UploadFile, user=Depends(escrita), db=Depends(session, scope='function')
):
    # Um byte a mais basta para a leitura saber que o arquivo passou do limite.
    conteudo = await arquivo.read(planilha.LIMITE_BYTES + 1)
    return await service.previa_importacao(db, conteudo, arquivo.filename, user)


@router.get(
    '/importacoes/ultima',
    response_model=ImportacaoConfirmada | None,
    dependencies=[Depends(usuario_atual)],
)
async def ultima_importacao(db=Depends(session, scope='function')):
    return await service.ultima_importacao(db)


@router.post('/importacoes/{id_}/confirmar', response_model=ImportacaoConfirmada)
async def confirmar_importacao(
    id_: UUID, user=Depends(escrita), db=Depends(session, scope='function')
):
    return await service.confirmar_importacao(db, id_, user)


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


fila_router = APIRouter(prefix='/perdas', tags=['perdas'], dependencies=[Depends(usuario_atual)])


@fila_router.get('/fila', response_model=PaginaFila)
async def fila(
    filtro: Annotated[FiltroFila, Query()],
    page: int = Query(1, ge=1, le=1_000_000),
    size: int = Query(25, ge=1, le=100),
    db=Depends(session, scope='function'),
):
    return await service.fila(db, filtro, page, size)


@fila_router.get('/fila/export', response_class=Response, responses=ARQUIVO_EXCEL)
async def exportar_fila(
    filtro: Annotated[FiltroFila, Query()], db=Depends(session, scope='function')
):
    return _excel(await service.exportar_fila(db, filtro), 'fila-de-inspecao.xlsx')
