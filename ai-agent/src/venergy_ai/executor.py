"""Execução do SQL já conferido pela guarda, com a engine da role `ai_read`."""

import asyncio
import math
import time
from dataclasses import dataclass
from datetime import date, datetime, time as hora, timedelta
from decimal import Decimal
from typing import Any, Protocol

from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from venergy_ai.interface import BancoIndisponivel


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

    Um erro da consulta vira `ConsultaFalhou`, que o agente devolve ao modelo para
    corrigir. Um banco fora do ar vira `BancoIndisponivel`: não há SQL a corrigir.
    """

    def __init__(self, engine: AsyncEngine):
        self.engine = engine

    async def executar(self, sql: str) -> ResultadoSQL:
        inicio = time.monotonic()
        try:
            conexao = await self.engine.connect()
        except (SQLAlchemyError, OSError) as erro:
            raise BancoIndisponivel(_mensagem(erro)) from erro
        try:
            transacao = await conexao.begin()
            try:
                resultado = await conexao.exec_driver_sql(sql)
                colunas, linhas = [], []
                if resultado.returns_rows:
                    colunas = list(resultado.keys())
                    brutas = list(resultado)
                    colunas = _com_unidade_dos_intervalos(colunas, brutas)
                    linhas = [[_valor(v) for v in linha] for linha in brutas]
            finally:
                await _sem_mascarar_o_cancelamento(transacao.rollback())
        except TimeoutError as erro:
            # O command_timeout do asyncpg pode disparar antes do statement_timeout da role,
            # e o SQLAlchemy não traduz o TimeoutError dele.
            raise ConsultaFalhou('a consulta passou do tempo limite do banco') from erro
        except DBAPIError as erro:
            if erro.connection_invalidated:
                raise BancoIndisponivel(_mensagem(erro)) from erro
            raise ConsultaFalhou(_mensagem(erro)) from erro
        except SQLAlchemyError as erro:
            raise ConsultaFalhou(_mensagem(erro)) from erro
        except OSError as erro:
            raise BancoIndisponivel(_mensagem(erro)) from erro
        finally:
            await _sem_mascarar_o_cancelamento(conexao.close())
        return ResultadoSQL(colunas, linhas, round((time.monotonic() - inicio) * 1000))


async def _sem_mascarar_o_cancelamento(passo) -> None:
    """Roda o rollback ou o close do fim da consulta.

    Cancelada no meio (o teto de tempo do assistente), a conexão pode recusar o passo com
    "another operation is in progress". Esse erro não pode tomar o lugar do cancelamento:
    viraria `ConsultaFalhou`, o agente pediria outra consulta e o teto não valeria."""
    try:
        await passo
    except (SQLAlchemyError, OSError):
        tarefa = asyncio.current_task()
        if tarefa is None or not tarefa.cancelling():
            raise


def _com_unidade_dos_intervalos(colunas: list[str], linhas: list) -> list[str]:
    # Um interval vira horas: o nome da coluna passa a dizer isso, para "2 dias" não virar
    # "48 dias" na resposta.
    return [
        nome
        if nome.endswith('_horas') or not any(isinstance(linha[i], timedelta) for linha in linhas)
        else f'{nome}_em_horas'
        for i, nome in enumerate(colunas)
    ]


def _mensagem(erro: Exception) -> str:
    # O SQLAlchemy embrulha o erro do asyncpg ("<class '...'>: mensagem"); a causa traz só
    # a mensagem do Postgres, que é o que o modelo precisa para corrigir o SQL.
    original = getattr(erro, 'orig', None) or erro
    texto = str(original.__cause__ or original).strip()
    return texto.splitlines()[0] if texto else type(erro).__name__


def _valor(valor: Any) -> Any:
    """Converte o valor do Postgres num que vira JSON sem perder o sentido."""
    if valor is None or isinstance(valor, bool | int | str):
        return valor
    if isinstance(valor, float):
        # NaN e infinito não existem em JSON nem no jsonb da auditoria.
        return valor if math.isfinite(valor) else str(valor)
    if isinstance(valor, Decimal):
        if not valor.is_finite():
            return str(valor)
        return int(valor) if valor == valor.to_integral_value() else float(valor)
    if isinstance(valor, timedelta):
        # Um interval vira horas, a unidade do DEC e do CHI.
        return round(valor.total_seconds() / 3600, 4)
    if isinstance(valor, datetime | date | hora):
        return valor.isoformat()
    if isinstance(valor, list | tuple):
        return [_valor(v) for v in valor]
    if isinstance(valor, dict):
        return {str(k): _valor(v) for k, v in valor.items()}
    # UUID, bytes e os demais tipos viram texto.
    return str(valor)
