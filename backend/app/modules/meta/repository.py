from sqlalchemy import text


async def carga_atual(db):
    return (
        (
            await db.execute(
                text(
                    'SELECT id, batch_id, versao_contrato, sintetica, carregado_em, '
                    'periodo_inicio AS competencia_inicial, '
                    'periodo_fim AS competencia_mais_recente '
                    'FROM operations.cargas ORDER BY carregado_em DESC, id DESC LIMIT 1'
                )
            )
        )
        .mappings()
        .first()
    )


async def dimensoes(db):
    return (
        (
            await db.execute(
                text(
                    'SELECT municipio, bairro, classe, alimentador '
                    'FROM analytics.dim_uc ORDER BY id_uc'
                )
            )
        )
        .mappings()
        .all()
    )
