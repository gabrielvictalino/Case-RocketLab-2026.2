from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from app.modules.continuidade import repository
from app.modules.continuidade.schemas import Indicadores, Ranking, Serie
from app.modules.metricas import contexto


def indicadores(rows):
    if not rows:
        return Indicadores(chi=None, interrupcoes=None, numero_ucs=None, dec=None, fec=None)
    chi = sum((r['chi'] for r in rows), Decimal(0))
    interrupcoes = sum(r['interrupcoes'] for r in rows)
    # O contrato garante numero_ucs fixo. Conta cada alimentador uma vez no
    # período, mesmo que tenha várias competências selecionadas.
    ucs = sum({r['alimentador']: r['numero_ucs'] for r in rows}.values())

    def razao(numerador):
        return (Decimal(numerador) / ucs).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    return Indicadores(
        chi=chi, interrupcoes=interrupcoes, numero_ucs=ucs, dec=razao(chi), fec=razao(interrupcoes)
    )


async def serie(db, periodo, comparacao, recorte, sem_evento_atipico):
    ctx = await contexto(db, periodo, comparacao)
    rows = await repository.mensais(db, ctx.atual, recorte, sem_evento_atipico)
    por_mes = defaultdict(list)
    for row in rows:
        por_mes[row['competencia']].append(row)
    pontos = []
    mes = ctx.atual.inicio
    while mes <= ctx.atual.fim:
        pontos.append(dict(competencia=mes, **indicadores(por_mes[mes]).model_dump()))
        if mes == ctx.atual.fim:
            break
        mes = (
            mes.replace(year=mes.year + 1, month=1)
            if mes.month == 12
            else mes.replace(month=mes.month + 1)
        )
    return Serie(
        **ctx.metadados(),
        sem_evento_atipico=sem_evento_atipico,
        totais=indicadores(rows),
        serie=pontos,
    )


async def ranking(db, periodo, comparacao, recorte, sem_evento_atipico, ordem):
    ctx = await contexto(db, periodo, comparacao)
    rows = await repository.mensais(db, ctx.atual, recorte, sem_evento_atipico)
    por_alimentador = defaultdict(list)
    for row in rows:
        por_alimentador[row['alimentador']].append(row)
    causas = defaultdict(list)
    for row in await repository.causas(db, ctx.atual, recorte, sem_evento_atipico):
        causas[row['alimentador']].append(
            {k: row[k] for k in ('causa', 'ocorrencias', 'interrupcoes')}
        )
    itens = [
        dict(
            alimentador=alimentador,
            municipio=mensais[0]['municipio'],
            **indicadores(mensais).model_dump(),
            causas=causas[alimentador],
        )
        for alimentador, mensais in por_alimentador.items()
    ]

    # Ordena pelo índice exato, antes do arredondamento da resposta; código
    # desempata para manter o resultado determinístico.
    def chave(item):
        valor = (
            item['chi']
            if ordem == 'chi'
            else (item['chi'] if ordem == 'dec' else Decimal(item['interrupcoes']))
            / item['numero_ucs']
        )
        return -valor, item['alimentador']

    itens.sort(key=chave)
    return Ranking(
        **ctx.metadados(), sem_evento_atipico=sem_evento_atipico, ordem=ordem, ranking=itens
    )
