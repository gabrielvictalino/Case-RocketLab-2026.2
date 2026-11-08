import json
from uuid import uuid4

from sqlalchemy import text

SEM_ORDEM_ATIVA = """NOT EXISTS (
    SELECT 1 FROM operations.ordens_inspecao o
    WHERE o.id_uc = f.id_uc AND o.status IN ('ABERTA', 'EM_CAMPO')
)"""


def _condicoes_fila(filtro) -> tuple[str, dict]:
    campos = filtro.model_dump()
    condicoes = [f'u.{campo} = :{campo}' for campo, valor in campos.items() if valor is not None]
    return (' AND '.join(condicoes) if condicoes else 'TRUE'), campos


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


async def fila(db, filtro, page: int, size: int) -> dict:
    where, campos = _condicoes_fila(filtro)
    params = {**campos, 'limit': size, 'offset': (page - 1) * size}
    linhas = (
        (
            await db.execute(
                text(f"""
            WITH base AS (
                SELECT f.id_uc, u.municipio, u.bairro, u.classe, f.score, f.motivos,
                       f.energia_recuperar_kwh, f.energia_recuperar_reais
                FROM analytics.fila_inspecao f
                JOIN analytics.dim_uc u USING (id_uc)
                WHERE {where} AND {SEM_ORDEM_ATIVA}
            )
            SELECT agg.*, p.*, i.id_inspecao, i.data AS inspecao_data,
                   i.inspetor, i.resultado, i.tipo_irregularidade, i.kwh_recuperado, i.origem
            FROM (SELECT count(*) AS total,
                         coalesce(sum(energia_recuperar_kwh), 0.00) AS filtro_kwh,
                         coalesce(sum(energia_recuperar_reais), 0.00) AS filtro_reais
                  FROM base) agg
            LEFT JOIN LATERAL (
                SELECT * FROM base ORDER BY score DESC, id_uc ASC LIMIT :limit OFFSET :offset
            ) p ON true
            LEFT JOIN LATERAL (
                SELECT id_inspecao, data, inspetor, resultado, tipo_irregularidade,
                       kwh_recuperado, origem
                FROM portal_read.inspecoes WHERE id_uc = p.id_uc
                ORDER BY data DESC, (origem = 'portal') DESC, id_inspecao DESC LIMIT 1
            ) i ON true
            ORDER BY p.score DESC, p.id_uc ASC
            """),
                params,
            )
        )
        .mappings()
        .all()
    )
    items = []
    for linha in linhas:
        if linha['id_uc'] is None:
            continue
        item = {
            key: linha[key]
            for key in (
                'id_uc',
                'municipio',
                'bairro',
                'classe',
                'score',
                'motivos',
                'energia_recuperar_kwh',
                'energia_recuperar_reais',
            )
        }
        item['inspecao_anterior'] = None
        if linha['id_inspecao'] is not None:
            item['inspecao_anterior'] = {
                'id_inspecao': linha['id_inspecao'],
                'data': linha['inspecao_data'],
                **{
                    key: linha[key]
                    for key in (
                        'inspetor',
                        'resultado',
                        'tipo_irregularidade',
                        'kwh_recuperado',
                        'origem',
                    )
                },
            }
        items.append(item)
    return {
        'items': items,
        'total': linhas[0]['total'],
        'page': page,
        'size': size,
        'filtro_kwh': linhas[0]['filtro_kwh'],
        'filtro_reais': linhas[0]['filtro_reais'],
    }


async def fila_completa(db, filtro):
    """A fila inteira numa consulta só: a lateral da paginada faria uma busca por UC."""
    where, campos = _condicoes_fila(filtro)
    return (
        (
            await db.execute(
                text(f"""
            SELECT f.id_uc, u.municipio, u.bairro, u.classe, f.score, f.motivos,
                   f.energia_recuperar_kwh, f.energia_recuperar_reais,
                   i.data AS inspecao_data, i.resultado AS inspecao_resultado
            FROM analytics.fila_inspecao f
            JOIN analytics.dim_uc u USING (id_uc)
            LEFT JOIN (
                SELECT DISTINCT ON (id_uc) id_uc, data, resultado
                FROM portal_read.inspecoes
                ORDER BY id_uc, data DESC, (origem = 'portal') DESC, id_inspecao DESC
            ) i USING (id_uc)
            WHERE {where} AND {SEM_ORDEM_ATIVA}
            ORDER BY f.score DESC, f.id_uc ASC
            """),
                campos,
            )
        )
        .mappings()
        .all()
    )


async def ordens_em_campo(db):
    return (
        (
            await db.execute(
                text("""SELECT id, id_uc, inspetor FROM operations.ordens_inspecao
                WHERE status = 'EM_CAMPO' ORDER BY criado_em, id""")
            )
        )
        .mappings()
        .all()
    )


async def ordens_da_planilha(db, ids, ucs):
    return (
        (
            await db.execute(
                text("""SELECT id, id_uc, status, inspetor FROM operations.ordens_inspecao
                WHERE id = ANY(CAST(:ids AS uuid[]))
                   OR (id_uc = ANY(CAST(:ucs AS text[])) AND status IN ('ABERTA', 'EM_CAMPO'))"""),
                {'ids': ids, 'ucs': ucs},
            )
        )
        .mappings()
        .all()
    )


async def criar_importacao(db, id_, arquivo, autor, validas, erros, avisos):
    await db.execute(
        text("""INSERT INTO operations.importacoes (id, arquivo, autor, validas, erros, avisos)
        VALUES (:id, :arquivo, :autor, CAST(:validas AS jsonb), CAST(:erros AS jsonb),
                CAST(:avisos AS jsonb))"""),
        {
            'id': id_,
            'arquivo': arquivo,
            'autor': autor,
            'validas': json.dumps(validas, default=str),
            'erros': json.dumps(erros),
            'avisos': json.dumps(avisos),
        },
    )


async def importacao_bloqueada(db, id_):
    return (
        (
            await db.execute(
                text('SELECT * FROM operations.importacoes WHERE id=:id FOR UPDATE'), {'id': id_}
            )
        )
        .mappings()
        .first()
    )


async def fechar_importacao(db, id_, atualizadas, rejeitadas):
    return (
        (
            await db.execute(
                text("""UPDATE operations.importacoes
                SET status = 'CONFIRMADA', atualizadas = :atualizadas,
                    rejeitadas = CAST(:rejeitadas AS jsonb), confirmado_em = now()
                WHERE id = :id RETURNING *"""),
                {'id': id_, 'atualizadas': atualizadas, 'rejeitadas': json.dumps(rejeitadas)},
            )
        )
        .mappings()
        .one()
    )


async def ultima_importacao(db):
    return (
        (
            await db.execute(
                text("""SELECT * FROM operations.importacoes WHERE status = 'CONFIRMADA'
                ORDER BY confirmado_em DESC LIMIT 1""")
            )
        )
        .mappings()
        .first()
    )
