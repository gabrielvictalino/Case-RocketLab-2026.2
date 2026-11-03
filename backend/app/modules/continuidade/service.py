from collections import defaultdict
from decimal import Decimal

from app.modules.continuidade import repository
from app.modules.continuidade.schemas import Indicadores, Ranking, Serie
from app.modules.kpis.service import razao
from app.modules.metricas import contexto


def indicadores(row):
    return Indicadores(
        chi=row['chi'],
        interrupcoes=row['interrupcoes'],
        numero_ucs=row['numero_ucs'],
        dec=razao(row['chi'], row['numero_ucs']),
        fec=razao(row['interrupcoes'], row['numero_ucs']),
    )


async def serie(db, periodo, comparacao, recorte, sem_evento_atipico):
    ctx = await contexto(db, periodo, comparacao)
    rows = await repository.serie(db, ctx.atual, recorte, sem_evento_atipico)
    totais = await repository.totais(db, ctx.atual, recorte, sem_evento_atipico)
    return Serie(
        **ctx.metadados(),
        sem_evento_atipico=sem_evento_atipico,
        totais=indicadores(totais),
        serie=[dict(competencia=r['competencia'], **indicadores(r).model_dump()) for r in rows],
    )


async def ranking(db, periodo, comparacao, recorte, sem_evento_atipico, ordem):
    ctx = await contexto(db, periodo, comparacao)
    rows = await repository.ranking(db, ctx.atual, recorte, sem_evento_atipico)
    causas = defaultdict(list)
    for row in await repository.causas(db, ctx.atual, recorte, sem_evento_atipico):
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
    return Ranking(
        **ctx.metadados(), sem_evento_atipico=sem_evento_atipico, ordem=ordem, ranking=itens
    )
