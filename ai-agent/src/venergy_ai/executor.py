"""Execução do SQL já conferido pela guarda, com a engine da role `ai_read`."""

import time
from dataclasses import dataclass
from datetime import date, datetime, time as hora
from decimal import Decimal
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine


@dataclass(frozen=True)
class ResultadoSQL:
    colunas: list[str]
    linhas: list[list[Any]]
    duracao_ms: int


class ConsultaFalhou(RuntimeError):
    """O Postgres recusou ou interrompeu a consulta. A mensagem vai para a nova tentativa."""


class ExecutorSQL(Protocol):
    async def executar(self, sql: str) -> ResultadoSQL: ...


class ExecutorAiRead:
    """Roda cada consulta numa transação própria, sempre encerrada com `ROLLBACK`.

    A role já é só leitura e tem `statement_timeout`, mas a própria sessão pode mudar
    os dois com `SET`. O `ROLLBACK` desfaz o `SET` antes de a conexão voltar ao pool.
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def executar(self, sql: str) -> ResultadoSQL:
        inicio = time.monotonic()
        try:
            async with self.engine.connect() as conexao:
                transacao = await conexao.begin()
                try:
                    resultado = await conexao.exec_driver_sql(sql)
                    colunas, linhas = [], []
                    if resultado.returns_rows:
                        colunas = list(resultado.keys())
                        linhas = [[_valor(v) for v in linha] for linha in resultado]
                finally:
                    await transacao.rollback()
        except SQLAlchemyError as erro:
            mensagem = str(getattr(erro, 'orig', None) or erro).splitlines()[0]
            raise ConsultaFalhou(mensagem) from erro
        return ResultadoSQL(colunas, linhas, round((time.monotonic() - inicio) * 1000))


def _valor(valor: Any) -> Any:
    """Converte o valor do Postgres num que vira JSON sem perder o sentido."""
    if isinstance(valor, Decimal):
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, datetime | date | hora):
        return valor.isoformat()
    if isinstance(valor, UUID):
        return str(valor)
    return valor
