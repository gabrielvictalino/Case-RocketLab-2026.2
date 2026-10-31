from sqlalchemy import text


async def carga_atual(db):
    return (
        (
            await db.execute(
                text(
                    'SELECT id, batch_id, versao_contrato, sintetica, carregado_em, '
                    'periodo_inicio AS competencia_inicial, '
                    'periodo_fim AS competencia_mais_recente '
                    'FROM operations.cargas ORDER BY ordem_publicacao DESC LIMIT 1'
                )
            )
        )
        .mappings()
        .first()
    )


async def dimensoes(db):
    locais = (
        (
            await db.execute(
                text(
                    'SELECT DISTINCT municipio, bairro FROM analytics.dim_uc '
                    'ORDER BY municipio, bairro'
                )
            )
        )
        .mappings()
        .all()
    )
    classes = (
        await db.scalars(text('SELECT DISTINCT classe FROM analytics.dim_uc ORDER BY classe'))
    ).all()
    alimentadores = (
        await db.scalars(
            text('SELECT DISTINCT alimentador FROM analytics.dim_uc ORDER BY alimentador')
        )
    ).all()
    bairros = {}
    for local in locais:
        bairros.setdefault(local['municipio'], []).append(local['bairro'])
    return dict(
        municipios=list(bairros), bairros=bairros, classes=classes, alimentadores=alimentadores
    )
