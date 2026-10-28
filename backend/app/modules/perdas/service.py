from sqlalchemy.exc import IntegrityError

from app.core.errors import APIError
from app.modules.perdas import repository as repo
from app.modules.perdas.schemas import Lote


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


async def transicao(db, id_, acao, body, user):
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
    await repo.evento(db, id_, user['id'], acao.upper(), body.model_dump(mode='json'))
    return result
