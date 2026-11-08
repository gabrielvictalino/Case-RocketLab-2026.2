import asyncio
from collections import defaultdict
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.errors import APIError
from app.modules.perdas import planilha
from app.modules.perdas import repository as repo
from app.modules.perdas.schemas import (
    ImportacaoConfirmada,
    Lote,
    PaginaFila,
    PreviaImportacao,
    Resultado,
)

COLUNAS_FILA = (
    'UC',
    'Município',
    'Bairro',
    'Classe',
    'Score',
    'Motivos',
    'Energia a recuperar (kWh)',
    'Energia a recuperar (R$)',
    'Última inspeção',
    'Último resultado',
)
MOTIVO_POR_STATUS = {
    'ABERTA': 'Ordem ainda não foi despachada',
    'CONCLUIDA': 'Ordem já concluída',
    'CANCELADA': 'Ordem cancelada',
}


async def criar(db, body, user):
    criadas, rejeitadas = [], []
    for uc in body.ucs:
        snapshot = await repo.candidata(db, uc)
        if snapshot is None:
            rejeitadas.append({'id_uc': uc, 'motivo': 'UC fora da fila'})
            continue
        try:
            async with db.begin_nested():
                ordem = await repo.criar(db, uc, snapshot, user['id'])
                await repo.evento(db, ordem['id'], user['id'], 'CRIADA', dict(snapshot))
        except IntegrityError as exc:
            if 'uq_ordem_ativa' not in str(exc.orig):
                raise
            rejeitadas.append({'id_uc': uc, 'motivo': 'UC já possui ordem ativa'})
        else:
            criadas.append(ordem)
    return Lote(criadas=criadas, rejeitadas=rejeitadas)


async def transicao(db, id_, acao, body, user, origem=None):
    ordem = await repo.buscar_bloqueada(db, id_)
    if ordem is None:
        raise APIError(404, 'Ordem não encontrada', 'ORDEM_NAO_ENCONTRADA')
    permitidos = {
        'despachar': {'ABERTA'},
        'tentativas': {'EM_CAMPO'},
        'resultado': {'EM_CAMPO'},
        'cancelar': {'ABERTA', 'EM_CAMPO'},
    }
    if ordem['status'] not in permitidos[acao]:
        raise APIError(409, 'Transição inválida para o estado atual', 'TRANSICAO_INVALIDA')
    if acao == 'despachar':
        values = {'status': 'EM_CAMPO', 'inspetor': body.inspetor}
    elif acao == 'tentativas':
        values = {'status': 'ABERTA', 'inspetor': None}
    elif acao == 'cancelar':
        values = {'status': 'CANCELADA', 'motivo_cancelamento': body.motivo}
    else:
        values = {
            'status': 'CONCLUIDA',
            'resultado': body.resultado,
            'tipo_irregularidade': body.tipo_irregularidade,
            'kwh_recuperado': body.kwh_recuperado,
        }
        await repo.inspecao(db, ordem, body)
    result = await repo.atualizar(db, id_, user['id'], values)
    dados = body.model_dump(mode='json')
    if acao == 'tentativas':
        dados['inspetor'] = ordem['inspetor']
    if origem:
        dados['origem'] = origem
    await repo.evento(db, id_, user['id'], acao.upper(), dados)
    return result


async def exportar_fila(db, filtro) -> bytes:
    linhas = [
        (
            linha['id_uc'],
            linha['municipio'],
            linha['bairro'],
            linha['classe'],
            linha['score'],
            ' · '.join(linha['motivos']),
            linha['energia_recuperar_kwh'],
            linha['energia_recuperar_reais'],
            linha['inspecao_data'],
            linha['inspecao_resultado'],
        )
        for linha in await repo.fila_completa(db, filtro)
    ]
    return await asyncio.to_thread(planilha.gerar, 'Fila de inspeção', COLUNAS_FILA, linhas)


async def exportar_ordens(db) -> bytes:
    colunas = planilha.COLUNAS_CAMPO
    linhas = [
        (None, ordem['id_uc'], None, ordem['inspetor'], None, None, None, str(ordem['id']))
        for ordem in await repo.ordens_em_campo(db)
    ]
    return await asyncio.to_thread(planilha.gerar, 'Planilha de campo', colunas, linhas)


async def previa_importacao(db, conteudo, nome, user) -> PreviaImportacao:
    celulas = await asyncio.to_thread(planilha.ler, conteudo)
    normalizadas = [planilha.normalizar(numero, linha) for numero, linha in celulas]
    lidas = [linha for linha in normalizadas if isinstance(linha, planilha.LinhaLida)]
    erros = {
        linha.numero: linha.motivo
        for linha in normalizadas
        if isinstance(linha, planilha.LinhaComErro)
    }
    ordens = await repo.ordens_da_planilha(
        db,
        [linha.id_ordem for linha in lidas if linha.id_ordem],
        [linha.id_uc for linha in lidas if linha.id_ordem is None],
    )
    por_id = {ordem['id']: ordem for ordem in ordens}
    ativa_da_uc = {
        ordem['id_uc']: ordem for ordem in ordens if ordem['status'] in ('ABERTA', 'EM_CAMPO')
    }
    aceitas = []
    for linha in lidas:
        ordem, motivo = _ordem_da_linha(linha, por_id, ativa_da_uc)
        if motivo:
            erros[linha.numero] = motivo
        else:
            aceitas.append((linha, ordem))
    aceitas = _sem_ordem_repetida(aceitas, erros)
    validas = [
        {
            'linha': linha.numero,
            'id_ordem': str(ordem['id']),
            'id_uc': ordem['id_uc'],
            'data': linha.resultado.data.isoformat(),
            'resultado': linha.resultado.resultado,
            'tipo_irregularidade': linha.resultado.tipo_irregularidade,
            'kwh_recuperado': str(linha.resultado.kwh_recuperado),
        }
        for linha, ordem in aceitas
    ]
    lista_erros = [{'linha': numero, 'motivo': erros[numero]} for numero in sorted(erros)]
    avisos = [{'linha': linha.numero, 'motivo': linha.aviso} for linha, _ in aceitas if linha.aviso]
    id_ = uuid4()
    arquivo = planilha.nome_do_arquivo(nome)
    await repo.criar_importacao(db, id_, arquivo, user['id'], validas, lista_erros, avisos)
    return PreviaImportacao(
        id=id_, arquivo=arquivo, validas=validas, erros=lista_erros, avisos=avisos
    )


def _ordem_da_linha(linha, por_id, ativa_da_uc):
    if linha.id_ordem:
        ordem = por_id.get(linha.id_ordem)
        if ordem is None:
            return None, 'Ordem não encontrada'
        if linha.id_uc and linha.id_uc != ordem['id_uc']:
            return None, f'A UC da linha não é a da ordem ({ordem["id_uc"]})'
    else:
        ordem = ativa_da_uc.get(linha.id_uc)
        if ordem is None:
            return None, 'UC sem ordem ativa'
    if ordem['status'] != 'EM_CAMPO':
        return None, MOTIVO_POR_STATUS[ordem['status']]
    if linha.inspetor and linha.inspetor != ordem['inspetor']:
        return None, f'Inspetor diferente do despachado na ordem ({ordem["inspetor"]})'
    return ordem, None


def _sem_ordem_repetida(aceitas, erros):
    # Como na Silver: escolher uma das versões de uma mesma ordem é decisão de quem preencheu.
    numeros = defaultdict(list)
    for linha, ordem in aceitas:
        numeros[ordem['id']].append(linha.numero)
    unicas = []
    for linha, ordem in aceitas:
        if len(numeros[ordem['id']]) == 1:
            unicas.append((linha, ordem))
        else:
            lista = ', '.join(map(str, numeros[ordem['id']]))
            erros[linha.numero] = f'Ordem repetida nas linhas {lista}'
    return unicas


async def confirmar_importacao(db, id_, user) -> ImportacaoConfirmada:
    importacao = await repo.importacao_bloqueada(db, id_)
    if importacao is None:
        raise APIError(404, 'Importação não encontrada', 'IMPORTACAO_NAO_ENCONTRADA')
    if importacao['status'] != 'PREVIA':
        raise APIError(409, 'Esta importação já foi confirmada', 'IMPORTACAO_JA_CONFIRMADA')
    if not importacao['validas']:
        raise APIError(409, 'A planilha não tem linhas válidas', 'IMPORTACAO_SEM_LINHAS')
    atualizadas, rejeitadas = 0, []
    # A ordem fixa evita deadlock entre duas confirmações que tocam as mesmas ordens.
    for linha in sorted(importacao['validas'], key=lambda item: item['id_ordem']):
        corpo = Resultado(
            resultado=linha['resultado'],
            tipo_irregularidade=linha['tipo_irregularidade'],
            kwh_recuperado=linha['kwh_recuperado'],
            data=linha['data'],
        )
        origem = {'importacao': str(id_), 'linha': linha['linha']}
        try:
            async with db.begin_nested():
                await transicao(db, UUID(linha['id_ordem']), 'resultado', corpo, user, origem)
        except APIError:
            rejeitadas.append(
                {'linha': linha['linha'], 'motivo': 'A ordem mudou de estado depois da prévia'}
            )
        else:
            atualizadas += 1
    rejeitadas.sort(key=lambda item: item['linha'])
    return _confirmada(await repo.fechar_importacao(db, id_, atualizadas, rejeitadas))


async def ultima_importacao(db) -> ImportacaoConfirmada | None:
    importacao = await repo.ultima_importacao(db)
    return None if importacao is None else _confirmada(importacao)


def _confirmada(importacao) -> ImportacaoConfirmada:
    return ImportacaoConfirmada(
        id=importacao['id'],
        arquivo=importacao['arquivo'],
        atualizadas=importacao['atualizadas'],
        rejeitadas=importacao['rejeitadas'],
        confirmado_em=importacao['confirmado_em'],
    )


async def fila(db, filtro, page, size) -> PaginaFila:
    resultado = await repo.fila(db, filtro, page, size)
    items = resultado['items']
    pagina = {
        'itens': len(items),
        'energia_recuperar_kwh': sum(
            (item['energia_recuperar_kwh'] for item in items), Decimal('0.00')
        ),
        'energia_recuperar_reais': sum(
            (item['energia_recuperar_reais'] for item in items), Decimal('0.00')
        ),
    }
    filtro_totais = {
        'itens': resultado['total'],
        'energia_recuperar_kwh': resultado['filtro_kwh'],
        'energia_recuperar_reais': resultado['filtro_reais'],
    }
    return PaginaFila(
        items=items,
        total=resultado['total'],
        page=page,
        size=size,
        totais={'pagina': pagina, 'filtro': filtro_totais},
    )
