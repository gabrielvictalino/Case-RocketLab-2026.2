"""Conferência de versões da exportação da Gold (gold-exportacao-portal.ipynb).

Funções puras sobre as linhas de DESCRIBE HISTORY (`version`, `timestamp`, `operation`),
testadas sem Spark em data-engineering/tests/test_gold_exportacao.py.
"""

# Commits Delta que não mudam os dados: não contam como nova versão do conteúdo
OPERACOES_SEM_DADOS = frozenset(
    {
        'SET TBLPROPERTIES',
        'UNSET TBLPROPERTIES',
        'COMPUTE STATS',
        'OPTIMIZE',
        'VACUUM START',
        'VACUUM END',
        'CHANGE COLUMN',
        'ADD CONSTRAINT',
        'DROP CONSTRAINT',
    }
)


def commits_de_dados(historico: list) -> list:
    """Os commits que mudam os dados, em ordem de versão. Um RESTORE muda os dados."""
    return sorted(
        (c for c in historico if c['operation'] not in OPERACOES_SEM_DADOS),
        key=lambda c: c['version'],
    )


def escrita_de_dados(historico: list, versao: int):
    """O commit que gravou o conteúdo da versão: o último de dados até ela.

    Uma versão de manutenção (OPTIMIZE, COMPUTE STATS, inclusive as do predictive optimization)
    tem o conteúdo da escrita anterior, e é o momento dessa escrita que conta.
    """
    antes = [c for c in commits_de_dados(historico) if c['version'] <= versao]
    if not antes:
        raise ValueError(f'Versão {versao} sem escrita de dados no histórico')
    return antes[-1]


def janela_de_dados(historico: list, versao: int) -> tuple:
    """Quando o conteúdo de uma versão passou a valer e quando foi trocado (None: ainda vale)."""
    depois = [c for c in commits_de_dados(historico) if c['version'] > versao]
    return escrita_de_dados(historico, versao)['timestamp'], (
        depois[0]['timestamp'] if depois else None
    )


def dentro_da_janela(momento, janela: tuple) -> bool:
    inicio, fim = janela
    return inicio < momento and (fim is None or momento < fim)


def dados_mudaram_depois(historico: list, versao: int) -> bool:
    """Se houve escrita de dados depois da versão; manutenção não conta."""
    return any(c['version'] > versao for c in commits_de_dados(historico))


def versao_do_marcador(historico: list, ids_na_versao, id_execucao: str) -> int:
    """A última versão de dados de um marcador de publicação que aponta para a execução.

    `ids_na_versao(versao)` devolve o conjunto de `id_execucao` do marcador naquela versão.
    Percorre do fim para o começo e para na primeira que bate (em geral, a atual).
    """
    for commit in reversed(commits_de_dados(historico)):
        if ids_na_versao(commit['version']) == {id_execucao}:
            return commit['version']
    raise ValueError(f'O marcador não tem versão que aponte para a execução {id_execucao}')
