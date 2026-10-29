import json
from uuid import uuid4

from sqlalchemy import text


async def candidata(db, id_uc):
    return (
        (
            await db.execute(
                text('SELECT * FROM analytics.fila_inspecao WHERE id_uc=:uc'), {'uc': id_uc}
            )
        )
        .mappings()
        .first()
    )


async def criar(db, id_uc, snapshot, autor):
    return (
        (
            await db.execute(
                text("""
        INSERT INTO operations.ordens_inspecao
          (id,id_uc,score,motivos,energia_recuperar_kwh,energia_recuperar_reais,
           criado_por,atualizado_por)
        VALUES (:id,:uc,:score,CAST(:motivos AS jsonb),:kwh,:reais,:autor,:autor)
        RETURNING *
    """),
                {
                    'id': uuid4(),
                    'uc': id_uc,
                    'score': snapshot['score'],
                    'motivos': json.dumps(snapshot['motivos']),
                    'kwh': snapshot['energia_recuperar_kwh'],
                    'reais': snapshot['energia_recuperar_reais'],
                    'autor': autor,
                },
            )
        )
        .mappings()
        .one()
    )


async def buscar_bloqueada(db, id_):
    return (
        (
            await db.execute(
                text('SELECT * FROM operations.ordens_inspecao WHERE id=:id FOR UPDATE'),
                {'id': id_},
            )
        )
        .mappings()
        .first()
    )


async def atualizar(db, id_, autor, values):
    # As chaves são definidas exclusivamente pelo serviço, nunca pelo corpo HTTP.
    setters = ', '.join(f'{key}=:{key}' for key in values)
    return (
        (
            await db.execute(
                text(
                    f'UPDATE operations.ordens_inspecao SET {setters}, '
                    'atualizado_por=:autor, atualizado_em=now() '
                    'WHERE id=:id RETURNING *'
                ),
                {'id': id_, 'autor': autor, **values},
            )
        )
        .mappings()
        .one()
    )


async def evento(db, id_, autor, tipo, dados):
    await db.execute(
        text(
            'INSERT INTO operations.ordem_eventos(id,id_ordem,autor,tipo,dados) '
            'VALUES (:id,:ordem,:autor,:tipo,CAST(:dados AS jsonb))'
        ),
        {
            'id': uuid4(),
            'ordem': id_,
            'autor': autor,
            'tipo': tipo,
            'dados': json.dumps(dados, default=str),
        },
    )


async def inspecao(db, ordem, body):
    await db.execute(
        text("""INSERT INTO operations.inspecoes
        (id_inspecao,id_uc,data,inspetor,resultado,tipo_irregularidade,kwh_recuperado,id_ordem)
        VALUES (:id,:uc,:data,:inspetor,:resultado,:tipo,:kwh,:ordem)"""),
        {
            'id': 'PORTAL-' + str(uuid4()),
            'uc': ordem['id_uc'],
            'data': body.data,
            'inspetor': ordem['inspetor'],
            'resultado': body.resultado,
            'tipo': body.tipo_irregularidade,
            'kwh': body.kwh_recuperado,
            'ordem': ordem['id'],
        },
    )


async def listar(db, status, page, size):
    params = {'status': status, 'limit': size, 'offset': (page - 1) * size}
    where = 'WHERE status=:status' if status else ''
    items = (
        (
            await db.execute(
                text(
                    f'SELECT * FROM operations.ordens_inspecao {where} '
                    'ORDER BY criado_em DESC, id LIMIT :limit OFFSET :offset'
                ),
                params,
            )
        )
        .mappings()
        .all()
    )
    total = await db.scalar(
        text(f'SELECT count(*) FROM operations.ordens_inspecao {where}'), params
    )
    return {'items': items, 'total': total, 'page': page, 'size': size}
