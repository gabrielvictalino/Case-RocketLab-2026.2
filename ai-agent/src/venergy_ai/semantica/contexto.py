"""Texto da camada semântica para o prompt do agente."""

from datetime import date

from venergy_ai.semantica.catalogo import VISOES, Coluna
from venergy_ai.semantica.periodo import Periodo, periodo_comparacao
from venergy_ai.semantica.vocabulario import LIMITES, VOCABULARIO


def descrever_semantica(
    periodo_padrao: Periodo | None = None,
    base: Periodo | None = None,
    data_referencia: date | None = None,
) -> str:
    """Catálogo, vocabulário, limites, carga e período padrão, em Markdown.

    `base` são as competências da carga publicada e `data_referencia`, a data do
    instantâneo financeiro do manifesto. Os dois vêm do banco a cada pergunta, para o
    texto não ficar para trás quando chega uma carga nova.
    """
    linhas = ['## Views de ai_read', '']
    for visao in VISOES:
        linhas += [
            f'### ai_read.{visao.nome}',
            visao.descricao,
            f'Grão: {visao.grao}. Chave: {", ".join(visao.chave)}. Período: {visao.periodo}',
        ]
        linhas += [linha_da_coluna(coluna) for coluna in visao.colunas]
        linhas += [f'Regra: {regra}' for regra in visao.regras]
        linhas.append('')
    linhas += ['## Vocabulário', '']
    for termo in VOCABULARIO:
        expressoes = ', '.join(f'"{e}"' for e in termo.expressoes)
        referencias = f' ({", ".join(termo.referencias)})' if termo.referencias else ''
        linhas.append(f'- {expressoes}: {termo.significado}{referencias}')
    linhas += ['', '## Limites: responda "não sei" quando a pergunta depender deles', '']
    if base is None:
        linhas.append('- A base cobre só as competências carregadas. Fora delas, não há dado.')
    else:
        linhas.append(
            f'- A base cobre as competências de {base.descricao} '
            f'({base.inicio.isoformat()} a {base.fim.isoformat()}). Fora disso, não há dado.'
        )
    linhas += [f'- {limite.descricao}' for limite in LIMITES]
    linhas += ['', '## Carga', '']
    if data_referencia is None:
        linhas.append(
            '- Sem data de referência das faturas: não responda sobre conta atrasada; '
            'responda sobre conta em aberto e diga que não dá para saber quais venceram.'
        )
    else:
        linhas.append(
            f'- Data de referência das faturas: {data_referencia.isoformat()}. Conta atrasada: '
            f"status_pagamento = 'ABERTA' AND data_vencimento < DATE "
            f"'{data_referencia.isoformat()}'."
        )
    linhas += ['', '## Período padrão', '']
    if periodo_padrao is None:
        linhas.append('Sem período na pergunta: os 12 meses até a competência mais recente.')
    else:
        linhas.append(
            f'Sem período na pergunta: {periodo_padrao.descricao} '
            f'({periodo_padrao.inicio.isoformat()} a {periodo_padrao.fim.isoformat()}).'
        )
        comparacao = periodo_comparacao(periodo_padrao, base and base.inicio)
        if comparacao is None:
            linhas.append(
                'Sem comparação padrão: o mesmo intervalo do ano anterior cai antes da base.'
            )
        else:
            linhas.append(
                f'Comparação padrão: {comparacao.descricao} '
                f'({comparacao.inicio.isoformat()} a {comparacao.fim.isoformat()}).'
            )
    linhas.append('A resposta sempre diz o período e a métrica usados.')
    return '\n'.join(linhas)


def linha_da_coluna(coluna: Coluna) -> str:
    unidade = f' [{coluna.unidade}]' if coluna.unidade else ''
    texto = f'- {coluna.nome}{unidade}: {coluna.descricao}'
    if coluna.valores:
        texto += f' Valores: {", ".join(coluna.valores)}.'
    if coluna.faixa is not None:
        texto += f' Escala de {coluna.faixa[0]} a {coluna.faixa[1]}.'
    return texto
