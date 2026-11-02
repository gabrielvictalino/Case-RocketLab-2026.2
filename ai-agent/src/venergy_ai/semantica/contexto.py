"""Texto da camada semântica para o prompt do agente."""

from venergy_ai.semantica.catalogo import VISOES
from venergy_ai.semantica.periodo import Periodo
from venergy_ai.semantica.vocabulario import LIMITES, VOCABULARIO


def descrever_semantica(periodo_padrao: Periodo | None = None) -> str:
    """Catálogo, vocabulário, limites e período padrão, em Markdown."""
    linhas = ['## Views de ai_read', '']
    for visao in VISOES:
        linhas += [
            f'### ai_read.{visao.nome}',
            visao.descricao,
            f'Grão: {visao.grao}. Chave: {", ".join(visao.chave)}. Período: {visao.periodo}',
        ]
        for coluna in visao.colunas:
            unidade = f' [{coluna.unidade}]' if coluna.unidade else ''
            linhas.append(f'- {coluna.nome}{unidade}: {coluna.descricao}')
        linhas += [f'Regra: {regra}' for regra in visao.regras]
        linhas.append('')
    linhas += ['## Vocabulário', '']
    for termo in VOCABULARIO:
        expressoes = ', '.join(f'"{e}"' for e in termo.expressoes)
        referencias = f' ({", ".join(termo.referencias)})' if termo.referencias else ''
        linhas.append(f'- {expressoes}: {termo.significado}{referencias}')
    linhas += ['', '## Limites: responda "não sei" quando a pergunta depender deles', '']
    linhas += [f'- {limite.descricao}' for limite in LIMITES]
    linhas += ['', '## Período padrão', '']
    if periodo_padrao is None:
        linhas.append('Sem período na pergunta: os 12 meses até a competência mais recente.')
    else:
        linhas.append(
            f'Sem período na pergunta: {periodo_padrao.descricao} '
            f'({periodo_padrao.inicio.isoformat()} a {periodo_padrao.fim.isoformat()}).'
        )
    linhas.append('A resposta sempre diz o período e a métrica usados.')
    return '\n'.join(linhas)
