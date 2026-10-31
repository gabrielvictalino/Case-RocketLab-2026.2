"""Guarda do SQL gerado pelo agente, aplicada antes de qualquer execução.

A guarda devolve o SQL regenerado a partir da árvore conferida, nunca o texto
recebido: comentários somem e o que o Postgres executa é o que foi validado.
A role `ai_read`, o `statement_timeout` e o `ROLLBACK` de cada consulta continuam
valendo como camadas independentes.
"""

from collections.abc import Collection

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, SqlglotError
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.optimizer.simplify import simplify

DIALETO = 'postgres'
SCHEMA = 'ai_read'
LIMITE_MAXIMO = 1000

# O sqlglot tipa as funções SQL comuns (agregação, data, texto, janela). As que ele
# não conhece chegam como Anonymous, e entre elas estão as administrativas do
# Postgres (pg_sleep, pg_read_file, dblink, lo_*, set_config...). Por isso uma
# função desconhecida só passa se estiver nesta lista.
FUNCOES_ANONIMAS_PERMITIDAS = frozenset(
    {
        'age',
        'cardinality',
        'every',
        'gcd',
        'isfinite',
        'jsonb_agg',
        'lcm',
        'make_date',
        'num_nonnulls',
        'num_nulls',
        'octet_length',
        'regexp_match',
        'regexp_matches',
        'regexp_split_to_array',
        'scale',
        'trim_scale',
    }
)


class SQLRejeitado(ValueError):
    """SQL barrado pela guarda; a mensagem é o motivo devolvido ao agente."""


def validar_sql(sql: str, views: Collection[str]) -> str:
    """Confere o SQL e devolve a versão que pode ser executada pela role `ai_read`.

    `views` são os nomes das views de `ai_read` que o catálogo do agente expõe.
    Nomes sem schema são qualificados com `ai_read`, e o `LIMIT` fica em no máximo
    `LIMITE_MAXIMO`. Levanta `SQLRejeitado` com o motivo, para a nova tentativa.
    """
    arvore = _uma_instrucao(sql)
    _conferir(arvore, views)
    _impor_limite(arvore)
    seguro = arvore.sql(dialect=DIALETO, comments=False)
    # Confere também o texto regenerado, que é o que o Postgres vai executar.
    _conferir(_uma_instrucao(seguro), views)
    return seguro


def _uma_instrucao(sql: str) -> exp.Expression:
    try:
        arvores = sqlglot.parse(sql, read=DIALETO)
    except ParseError as erro:
        detalhe = erro.errors[0]
        raise SQLRejeitado(
            f'SQL inválido: {detalhe["description"]} '
            f'(linha {detalhe["line"]}, coluna {detalhe["col"]}).'
        ) from erro
    except SqlglotError as erro:
        raise SQLRejeitado(f'SQL inválido: {erro}.') from erro
    instrucoes = [a for a in arvores if a is not None and not isinstance(a, exp.Semicolon)]
    if len(instrucoes) != 1:
        raise SQLRejeitado(
            f'Envie exatamente uma instrução SQL; foram recebidas {len(instrucoes)}.'
        )
    return instrucoes[0]


def _conferir(arvore: exp.Expression, views: Collection[str]) -> None:
    if not isinstance(arvore, (exp.Select, exp.SetOperation)):
        raise SQLRejeitado('Só é permitido SELECT, com ou sem WITH.')
    normalize_identifiers(arvore, dialect=DIALETO)
    for no in arvore.walk():
        # Dentro de um SELECT, o Postgres só aceita escrita num WITH:
        # WITH d AS (DELETE ... RETURNING *) SELECT ...
        if isinstance(no, exp.DML):
            raise SQLRejeitado(f'Escrita não é permitida: {no.key.upper()}.')
        if isinstance(no, exp.Into):
            raise SQLRejeitado('SELECT INTO cria uma tabela e não é permitido.')
        if isinstance(no, exp.Lock):
            raise SQLRejeitado('FOR UPDATE/FOR SHARE trava linhas e não é permitido.')
        # 'operations.usuarios'::regclass consulta o catálogo do Postgres por fora das views.
        catalogo = isinstance(no, exp.DataType) and no.this == exp.DataType.Type.USERDEFINED
        if isinstance(no, exp.ObjectIdentifier) or catalogo:
            raise SQLRejeitado(
                f'Conversão para tipo do catálogo não é permitida: {no.sql(dialect=DIALETO)}.'
            )
    _conferir_funcoes(arvore)
    _conferir_tabelas(arvore, views)


def _conferir_funcoes(arvore: exp.Expression) -> None:
    for funcao in arvore.find_all(exp.Func):
        if isinstance(funcao.parent, exp.Dot) and funcao.arg_key == 'expression':
            raise SQLRejeitado(
                f'Função com schema não é permitida: {funcao.parent.sql(dialect=DIALETO)}.'
            )
        anonima = isinstance(funcao, (exp.Anonymous, exp.AnonymousAggFunc))
        if anonima and funcao.name.lower() not in FUNCOES_ANONIMAS_PERMITIDAS:
            raise SQLRejeitado(
                f'Função não permitida: {funcao.name}. '
                'Use funções SQL de agregação, data, texto e janela.'
            )


def _conferir_tabelas(arvore: exp.Expression, views: Collection[str]) -> None:
    try:
        escopos = traverse_scope(arvore)
    except SqlglotError as erro:
        raise SQLRejeitado(f'Não foi possível identificar as tabelas: {erro}.') from erro
    # Uma referência sem schema só é CTE se o nome estiver no escopo dela; fora
    # dele, o Postgres procuraria uma tabela com esse nome.
    ctes = {
        id(tabela)
        for escopo in escopos
        for tabela in escopo.tables
        if not tabela.db and tabela.name in escopo.cte_sources
    }
    for tabela in arvore.find_all(exp.Table):
        if id(tabela) in ctes or isinstance(tabela.this, exp.Func):
            continue
        if not isinstance(tabela.this, exp.Identifier):
            raise SQLRejeitado(f'Origem de dados não suportada: {tabela.sql(dialect=DIALETO)}.')
        if tabela.catalog or tabela.db not in ('', SCHEMA) or tabela.name not in views:
            raise SQLRejeitado(
                f'Tabela fora do catálogo do agente: {tabela.sql(dialect=DIALETO)}. '
                f'Use só as views de {SCHEMA}: {", ".join(sorted(views))}.'
            )
        tabela.set('db', exp.to_identifier(SCHEMA))


def _impor_limite(arvore: exp.Expression) -> None:
    linhas = _linhas_pedidas(arvore.args.get('limit'))
    if linhas is None or linhas > LIMITE_MAXIMO:
        linhas = LIMITE_MAXIMO
    arvore.set('limit', exp.Limit(expression=exp.Literal.number(linhas)))


def _linhas_pedidas(limite: exp.Expression | None) -> int | None:
    """Linhas pedidas no LIMIT ou no FETCH; None quando a consulta não tem limite."""
    if limite is None:
        return None
    if isinstance(limite, exp.Fetch):
        opcoes = limite.args.get('limit_options')
        if opcoes and opcoes.args.get('with_ties'):
            raise SQLRejeitado(
                'FETCH ... WITH TIES pode passar do limite de linhas e não é permitido. '
                'Use LIMIT n, ou rank() OVER (...) <= n para manter os empates.'
            )
        if opcoes and opcoes.args.get('percent'):
            raise SQLRejeitado('FETCH ... PERCENT não existe no Postgres. Use LIMIT n.')
        valor = limite.args.get('count')
        if valor is None:
            return 1  # FETCH FIRST ROW ONLY
    elif isinstance(limite, exp.Limit):
        valor = limite.expression
        # LIMIT ALL e LIMIT NULL equivalem a não ter limite.
        if isinstance(valor, exp.Null) or (isinstance(valor, exp.Var) and valor.name == 'ALL'):
            return None
    else:
        raise SQLRejeitado(f'Limite não suportado: {limite.sql(dialect=DIALETO)}. Use LIMIT n.')
    valor = simplify(valor.copy(), dialect=DIALETO)
    # O Postgres aceita LIMIT '5', convertendo o texto em número.
    if valor.is_string and valor.name.isascii() and valor.name.isdigit():
        return int(valor.name)
    if valor.is_int and valor.to_py() >= 0:
        return valor.to_py()
    raise SQLRejeitado(
        f'O limite precisa ser um inteiro não negativo, como LIMIT 10: '
        f'{valor.sql(dialect=DIALETO)}.'
    )
