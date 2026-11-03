from collections import defaultdict
from decimal import Decimal

from app.modules.continuidade import repository
from app.modules.continuidade.schemas import Indicadores, Ranking, Serie, SeriePeriodo
from app.modules.metricas import contexto, razao


def indicadores(row):
    return Indicadores(
        chi=row['chi'],
        interrupcoes=row['interrupcoes'],
        numero_ucs=row['numero_ucs'],
        dec=razao(row['chi'], row['numero_ucs']),
        fec=razao(row['interrupcoes'], row['numero_ucs']),
    )


async def serie_periodo(db, periodo, recorte, sem_evento_atipico):
    rows = await repository.serie(db, periodo, recorte, sem_evento_atipico)
    totais = {k: rows[0][f'total_{k}'] for k in ('chi', 'interrupcoes', 'numero_ucs')}
    return SeriePeriodo(
        totais=indicadores(totais),
        serie=[dict(competencia=r['competencia'], **indicadores(r).model_dump()) for r in rows],
    )


async def serie(db, periodo, comparacao, recorte, sem_evento_atipico):
    ctx = await contexto(db, periodo, comparacao)
    atual = await serie_periodo(db, ctx.atual, recorte, sem_evento_atipico)
    anterior = (
        await serie_periodo(db, ctx.anterior, recorte, sem_evento_atipico) if ctx.anterior else None
    )
    return Serie(
        **ctx.metadados(),
        sem_evento_atipico=sem_evento_atipico,
        **atual.model_dump(),
        dados_comparacao=anterior,
    )


async def ranking_periodo(db, periodo, recorte, sem_evento_atipico, ordem):
    rows = await repository.ranking(db, periodo, recorte, sem_evento_atipico)
    causas = defaultdict(list)
    for row in await repository.causas(db, periodo, recorte, sem_evento_atipico):
        causas[row['alimentador']].append(
            {k: row[k] for k in ('causa', 'ocorrencias', 'interrupcoes')}
        )
    itens = []
    for row in rows:
        valores = indicadores(row)
        if valores.dec is None:
            continue
        itens.append(
            dict(
                alimentador=row['alimentador'],
                municipio=row['municipio'],
                **valores.model_dump(),
                causas=causas[row['alimentador']],
            )
        )

    # Ordena pelo índice exato, antes do arredondamento da resposta; código
    # desempata para manter o resultado determinístico. UCs zero são omitidas acima.
    def chave(item):
        valores = {
            'chi': item['chi'],
            'dec': item['chi'] / item['numero_ucs'],
            'fec': Decimal(item['interrupcoes']) / item['numero_ucs'],
        }
        return -valores[ordem], item['alimentador']

    itens.sort(key=chave)
    return itens


async def ranking(db, periodo, comparacao, recorte, sem_evento_atipico, ordem):
    ctx = await contexto(db, periodo, comparacao)
    atual = await ranking_periodo(db, ctx.atual, recorte, sem_evento_atipico, ordem)
    anterior = (
        await ranking_periodo(db, ctx.anterior, recorte, sem_evento_atipico, ordem)
        if ctx.anterior
        else None
    )
    return Ranking(
        **ctx.metadados(),
        sem_evento_atipico=sem_evento_atipico,
        ordem=ordem,
        ranking=atual,
        ranking_comparacao=anterior,
    )
