"""Texto da camada semântica para o prompt do agente."""

from datetime import date
from functools import cache

from venergy_ai.semantica.catalogo import VISOES, Coluna, Visao
from venergy_ai.semantica.periodo import Periodo, deslocar, periodo_comparacao
from venergy_ai.semantica.vocabulario import LIMITES, VOCABULARIO


def descrever_semantica(base: Periodo | None = None, data_referencia: date | None = None) -> str:
    """Catálogo, vocabulário, limites e o que a carga publicada diz, em Markdown.

    `base` são as competências da carga e `data_referencia`, a data do instantâneo
    financeiro do manifesto. Os dois vêm do banco a cada pergunta, para o texto não ficar
    para trás quando chega uma carga nova; o resto não muda e é montado uma vez só.
    """
    return '\n'.join((_texto_fixo(), _carga(base, data_referencia)))


def descrever_periodo_padrao(padrao: Periodo, inicio_base: date | None = None) -> str:
    """O período de uma pergunta que não diz qual, e a comparação dele.

    Quem escolhe o período é o agente (o da conversa, o da tela ou os últimos 12 meses
    da base), então ele não sai da carga. A comparação é o ano anterior, se couber na base.
    """
    linhas = ['## Período padrão', '', f'Sem período na pergunta: {_periodo(padrao)}']
    comparacao = periodo_comparacao(padrao, inicio_base)
    if comparacao is None:
        linhas.append('Sem comparação padrão: o mesmo intervalo do ano anterior cai antes da base.')
    else:
        linhas.append(f'Comparação padrão: {_periodo(comparacao)}')
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


def filtro_do_periodo(visao: Visao) -> str | None:
    """Como filtrar a coluna de tempo da view por um período de competências."""
    coluna = visao.coluna_tempo
    if coluna is None:
        return None
    if coluna == 'competencia':
        return "competencia BETWEEN DATE '<primeiro mês>' AND DATE '<último mês>'."
    # Data ou data e hora: um BETWEEN até o dia 1 do último mês perderia quase todo ele.
    return (
        f"{coluna} >= DATE '<primeiro mês>' AND {coluna} < DATE '<último mês>' + "
        "INTERVAL '1 month'. O último mês entra inteiro."
    )


@cache
def _texto_fixo() -> str:
    linhas = ['## Views de ai_read', '']
    for visao in VISOES:
        linhas += [
            f'### ai_read.{visao.nome}',
            visao.descricao,
            f'Grão: {visao.grao}. Chave: {", ".join(visao.chave)}. Período: {visao.periodo}',
        ]
        if (filtro := filtro_do_periodo(visao)) is not None:
            linhas.append(f'Filtro de período: {filtro}')
        linhas += [linha_da_coluna(coluna) for coluna in visao.colunas]
        linhas += [f'Regra: {regra}' for regra in visao.regras]
        linhas.append('')
    linhas += ['## Vocabulário', '']
    for termo in VOCABULARIO:
        expressoes = ', '.join(f'"{e}"' for e in termo.expressoes)
        referencias = f' ({", ".join(termo.referencias)})' if termo.referencias else ''
        linhas.append(f'- {expressoes}: {termo.significado}{referencias}')
    linhas += ['', '## Limites: responda "não sei" quando a pergunta depender deles', '']
    linhas += [f'- {limite.descricao}' for limite in LIMITES]
    return '\n'.join(linhas)


def _carga(base: Periodo | None, data_referencia: date | None) -> str:
    linhas = ['', '## Carga', '']
    if base is None:
        linhas.append(
            '- Os dados da carga cobrem só as competências carregadas. Fora delas, não há dado '
            'da carga.'
        )
    else:
        linhas.append(
            f'- Os dados da carga cobrem as competências de {base.descricao} '
            f'({base.inicio.isoformat()} a {base.fim.isoformat()}). Fora disso, não há dado '
            'da carga.'
        )
    # As inspeções do portal e as ordens ativas da fila não esperam a próxima carga.
    linhas.append(
        "- Exceção: as inspeções com origem = 'portal' são concluídas no portal e podem ter "
        'data depois da carga. Numa pergunta sobre elas, não diga "não sei" só pelo período.'
    )
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
    return '\n'.join(linhas)


def _periodo(periodo: Periodo) -> str:
    # Os dois filtros já com as datas: o modelo não precisa somar o mês.
    inicio, fim = periodo.inicio.isoformat(), periodo.fim.isoformat()
    depois = deslocar(periodo.fim, 1).isoformat()
    return (
        f"{periodo.descricao}. Em competencia: BETWEEN DATE '{inicio}' AND DATE '{fim}'. "
        f"Em data ou data e hora: >= DATE '{inicio}' AND < DATE '{depois}'."
    )
