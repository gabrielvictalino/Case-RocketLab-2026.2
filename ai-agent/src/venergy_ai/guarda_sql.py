"""Guarda do SQL gerado pelo agente, aplicada antes de qualquer execução.

A guarda devolve o SQL regenerado a partir da árvore conferida, nunca o texto
recebido: comentários somem e o que o Postgres executa é o que foi validado.
A role `ai_read`, o `statement_timeout` e o `ROLLBACK` de cada consulta continuam
valendo como camadas independentes.
"""

from collections.abc import Collection

import sqlglot
from sqlglot import exp
from sqlglot.dialects.dialect import rename_func
from sqlglot.dialects.postgres import Postgres
from sqlglot.errors import ParseError, SqlglotError
from sqlglot.optimizer.normalize_identifiers import normalize_identifiers
from sqlglot.optimizer.scope import traverse_scope
from sqlglot.optimizer.simplify import simplify

SCHEMA = 'ai_read'
LIMITE_MAXIMO = 1000

# O sqlglot tipa as funções SQL comuns (agregação, data, texto, janela). As que ele
# não conhece chegam como Anonymous, e entre elas estão as administrativas do
# Postgres (pg_sleep, pg_read_file, dblink, lo_*, set_config...). Por isso uma
# função desconhecida só passa se estiver nesta lista.
FUNCOES_ANONIMAS_PERMITIDAS = frozenset(
    {
        'age',
        'array_lower',
        'array_upper',
        'cardinality',
        'clock_timestamp',
        'every',
        'gcd',
        'isfinite',
        'json_array_length',
        'json_build_array',
        'json_build_object',
        'json_typeof',
        'jsonb_agg',
        'jsonb_array_length',
        'jsonb_build_array',
        'jsonb_build_object',
        'jsonb_extract_path_text',
        'jsonb_typeof',
        'lcm',
        'make_date',
        'num_nonnulls',
        'num_nulls',
        'octet_length',
        'regexp_match',
        'regexp_matches',
        'regexp_split_to_array',
        'scale',
        'statement_timestamp',
        'timezone',
        'to_json',
        'to_jsonb',
        'transaction_timestamp',
        'trim_scale',
    }
)

# Em `x = ALL(ARRAY[...])` o sqlglot lê ALL e SOME como função. No Postgres são
# palavras reservadas, e nenhuma função pode ser chamada por esses nomes sem aspas.
CONSTRUCOES_ANONIMAS = frozenset({'all', 'some'})


class PostgresDaGuarda(Postgres):
    """Dialeto Postgres com as correções de que o SQL regenerado precisa."""

    class Generator(Postgres.Generator):
        # O sqlglot gera to_hex como HEX, que não existe no Postgres.
        TRANSFORMS = {**Postgres.Generator.TRANSFORMS, exp.Hex: rename_func('TO_HEX')}


DIALETO = PostgresDaGuarda


class SQLRejeitado(ValueError):
    """SQL barrado pela guarda; a mensagem é o motivo devolvido ao agente."""


def validar_sql(sql: str, views: Collection[str]) -> str:
    """Confere o SQL e devolve a versão que pode ser executada pela role `ai_read`.

    `views` são os nomes das views de `ai_read` que o catálogo do agente expõe.
    Nomes sem schema são qualificados com `ai_read`, e o `LIMIT` fica em no máximo
    `LIMITE_MAXIMO`. Levanta `SQLRejeitado` com o motivo, para a nova tentativa.
    """
    # O Postgres guarda em minúsculas os nomes criados sem aspas.
    views = frozenset(view.lower() for view in views)
    try:
        arvore = _uma_instrucao(sql)
        for tabela in _conferir(arvore, views):
            tabela.set('db', exp.to_identifier(SCHEMA))
        _impor_limite(arvore)
        seguro = arvore.sql(dialect=DIALETO, comments=False)
        # Confere também o texto regenerado, que é o que o Postgres vai executar.
        _conferir_regenerado(_uma_instrucao(seguro), views)
    except RecursionError as erro:
        raise SQLRejeitado(
            'A consulta tem aninhamento demais. Simplifique as subconsultas e expressões.'
        ) from erro
    except SqlglotError as erro:
        raise SQLRejeitado(f'SQL inválido: {erro}.') from erro
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
    instrucoes = [a for a in arvores if a is not None and not isinstance(a, exp.Semicolon)]
    if len(instrucoes) != 1:
        raise SQLRejeitado(
            f'Envie exatamente uma instrução SQL; foram recebidas {len(instrucoes)}.'
        )
    return instrucoes[0]


def _conferir(arvore: exp.Expression, views: frozenset[str]) -> list[exp.Table]:
    """Levanta `SQLRejeitado` no que não é permitido e devolve as views lidas."""
    if not isinstance(arvore, (exp.Select, exp.SetOperation)):
        raise SQLRejeitado('Só é permitido SELECT, com ou sem WITH.')
    normalize_identifiers(arvore, dialect=DIALETO)
    tabelas = []
    for no in arvore.walk():
        # Dentro de um SELECT, o Postgres só aceita escrita num WITH:
        # WITH d AS (DELETE ... RETURNING *) SELECT ...
        if isinstance(no, exp.DML):
            raise SQLRejeitado(f'Escrita não é permitida: {no.key.upper()}.')
        if isinstance(no, exp.Into):
            raise SQLRejeitado('SELECT INTO cria uma tabela e não é permitido.')
        if isinstance(no, exp.Lock):
            raise SQLRejeitado('FOR UPDATE/FOR SHARE trava linhas e não é permitido.')
        # O sqlglot regenera :x e @x em formas que o Postgres não aceita.
        if isinstance(no, (exp.Parameter, exp.Placeholder)):
            raise SQLRejeitado(
                'Parâmetros (:nome, $1, @nome, ?) não são permitidos. Escreva os valores '
                'na própria consulta; para valor absoluto, use abs().'
            )
        # 'operations.usuarios'::regclass consulta o catálogo do Postgres por fora das views.
        catalogo = isinstance(no, exp.DataType) and no.this == exp.DataType.Type.USERDEFINED
        if isinstance(no, exp.ObjectIdentifier) or catalogo:
            raise SQLRejeitado(
                f'Conversão para tipo do catálogo não é permitida: {no.sql(dialect=DIALETO)}.'
            )
        if isinstance(no, exp.Func):
            _conferir_funcao(no)
        elif isinstance(no, exp.Table):
            tabelas.append(no)
    # As tabelas ficam por último: uma escrita num WITH chegaria aqui como tabela
    # desconhecida, e o motivo devolvido ao agente deve ser a escrita.
    ctes = _referencias_a_cte(arvore)
    return [tabela for tabela in tabelas if id(tabela) not in ctes and _e_view(tabela, views)]


def _referencias_a_cte(arvore: exp.Expression) -> set[int]:
    try:
        escopos = traverse_scope(arvore)
    except SqlglotError as erro:
        raise SQLRejeitado(f'Não foi possível identificar as tabelas: {erro}.') from erro
    # Uma referência sem schema só é CTE se o nome estiver no escopo dela; fora
    # dele, o Postgres procuraria uma tabela com esse nome.
    return {
        id(tabela)
        for escopo in escopos
        for tabela in escopo.tables
        if not tabela.db and tabela.name in escopo.cte_sources
    }


def _conferir_funcao(funcao: exp.Func) -> None:
    if isinstance(funcao.parent, exp.Dot) and funcao.arg_key == 'expression':
        raise SQLRejeitado(
            f'Função com schema não é permitida: {funcao.parent.sql(dialect=DIALETO)}.'
        )
    if not isinstance(funcao, (exp.Anonymous, exp.AnonymousAggFunc)):
        return
    nome = funcao.name.lower()
    if nome not in FUNCOES_ANONIMAS_PERMITIDAS and nome not in CONSTRUCOES_ANONIMAS:
        raise SQLRejeitado(
            f'Função não permitida: {funcao.name}. '
            'Use funções SQL de agregação, data, texto e janela.'
        )
    # Entre aspas o nome não vira minúsculas, e o sqlglot o regenera em maiúsculas.
    if isinstance(funcao.this, exp.Identifier) and funcao.this.quoted:
        raise SQLRejeitado(f'Escreva o nome da função sem aspas: {funcao.name}.')


def _e_view(tabela: exp.Table, views: frozenset[str]) -> bool:
    if isinstance(tabela.this, exp.Func):
        # A função de um FROM (generate_series, unnest) é conferida como as demais.
        if tabela.catalog or tabela.db:
            raise SQLRejeitado(f'Função com schema não é permitida: {tabela.sql(dialect=DIALETO)}.')
        return False
    if not isinstance(tabela.this, exp.Identifier):
        raise SQLRejeitado(f'Origem de dados não suportada: {tabela.sql(dialect=DIALETO)}.')
    if tabela.catalog or tabela.db not in ('', SCHEMA) or tabela.name not in views:
        raise SQLRejeitado(
            f'Tabela fora do catálogo do agente: {tabela.sql(dialect=DIALETO)}. '
            f'Use só as views de {SCHEMA}: {", ".join(sorted(views))}.'
        )
    return True


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


def _conferir_regenerado(arvore: exp.Expression, views: frozenset[str]) -> None:
    tabelas = _conferir(arvore, views)
    if any(tabela.db != SCHEMA for tabela in tabelas):
        raise SQLRejeitado(f'Não foi possível qualificar as views com {SCHEMA}.')
    limite = arvore.args.get('limit')
    valor = limite.expression if isinstance(limite, exp.Limit) else None
    if not (isinstance(valor, exp.Literal) and valor.is_int and valor.to_py() <= LIMITE_MAXIMO):
        raise SQLRejeitado(f'Não foi possível garantir o LIMIT {LIMITE_MAXIMO}.')
