"""Agente Text-to-SQL: pergunta → plano → SQL → guarda → execução → resposta.

O fluxo é orquestrado aqui, não pelo modelo: são duas chamadas ao LLM (plano e
redação), mais uma de correção quando o SQL falha. Assim o número de tentativas
é fixo e cada passo pode ser testado com o modelo simulado.
"""

import time
from datetime import date
from typing import Literal

import pydantic_ai
import sqlglot
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, ModelAPIError, ModelSettings, UnexpectedModelBehavior
from pydantic_ai.models import Model
from sqlglot import exp

from venergy_ai.executor import ConsultaFalhou, ExecutorSQL
from venergy_ai.guarda_sql import DIALETO, LIMITE_MAXIMO, SQLRejeitado, validar_sql
from venergy_ai.instrucoes import (
    INSTRUCOES_REDACAO,
    instrucoes_do_plano,
    pedido_de_correcao,
    pedido_de_redacao,
    pergunta_delimitada,
)
from venergy_ai.interface import (
    LINHAS_EXIBIDAS,
    Andamento,
    BancoIndisponivel,
    Consulta,
    Contexto,
    PeriodoUsado,
    ProvedorIndisponivel,
    RespostaAgente,
)
from venergy_ai.numeros import numeros_citados, numeros_sem_lastro
from venergy_ai.semantica import VISOES_POR_NOME, Periodo, periodo_padrao

# O banner do PydanticAI sai na saída padrão na primeira execução: no backend é só ruído.
pydantic_ai.BANNER_ENABLED = False

# A primeira consulta e no máximo uma nova tentativa.
TENTATIVAS_SQL = 2
CONFIGURACAO = ModelSettings(temperature=0, timeout=20)
# O motivo do "não sei" é texto do modelo: com número que não se sustenta, sai este.
MOTIVO_SEM_DADO = 'Os dados disponíveis não respondem a essa pergunta.'


class Plano(BaseModel):
    """Primeiro passo: como a pergunta vira consulta, antes de qualquer texto."""

    tipo: Literal['consulta', 'fora_do_dominio', 'sem_dado'] = Field(
        description='consulta quando as views respondem; senão fora_do_dominio ou sem_dado.'
    )
    metrica: str | None = Field(
        None, description='Métrica usada, com a unidade. Ex.: "Receita faturada (R$)".'
    )
    filtros: list[str] = Field(
        default_factory=list, description='Filtros aplicados. Ex.: "município = Recife".'
    )
    periodo_inicio: date | None = Field(None, description='Primeira competência, AAAA-MM-01.')
    periodo_fim: date | None = Field(None, description='Última competência, AAAA-MM-01.')
    sql: str | None = Field(None, description='Uma única consulta SELECT nas views de ai_read.')
    motivo: str | None = Field(
        None, description='Quando não há consulta: por que os dados não respondem.'
    )
    alternativa: str | None = Field(
        None, description='Uma pergunta parecida que os dados respondem, se houver.'
    )

    @model_validator(mode='after')
    def _completo(self):
        if self.tipo == 'consulta' and not (self.sql and self.metrica):
            raise ValueError('Uma consulta precisa de sql e de metrica.')
        if self.tipo != 'consulta' and not self.motivo:
            raise ValueError('Explique o motivo quando não houver consulta.')
        return self


class AgenteTextoSQL:
    """Implementa `Assistente`. Só recebe o modelo e o executor da role `ai_read`."""

    def __init__(self, modelo: Model, executor: ExecutorSQL):
        self.modelo = modelo
        self.executor = executor
        self.planejador = Agent(modelo, output_type=Plano, model_settings=CONFIGURACAO, retries=1)
        self.redator = Agent(
            modelo, instructions=INSTRUCOES_REDACAO, model_settings=CONFIGURACAO, retries=1
        )

    async def responder(
        self, pergunta: str, contexto: Contexto, andamento: Andamento | None = None
    ) -> RespostaAgente:
        """`andamento` é preenchido aos poucos: quem chama audita também uma pergunta que
        falhou (`ProvedorIndisponivel`, `BancoIndisponivel`) ou foi cancelada por tempo."""
        inicio = time.monotonic()
        andamento = Andamento() if andamento is None else andamento
        andamento.modelo = self.modelo.model_name
        try:
            campos = await self._responder(pergunta, contexto, andamento)
        except ModelAPIError as erro:
            raise ProvedorIndisponivel(str(erro)) from erro
        except UnexpectedModelBehavior:
            campos = _nao_sei('O modelo não devolveu a resposta no formato esperado.')
        return RespostaAgente(
            **campos,
            consultas=andamento.consultas,
            modelo=self.modelo.model_name,
            tokens_entrada=andamento.tokens_entrada,
            tokens_saida=andamento.tokens_saida,
            latencia_ms=round((time.monotonic() - inicio) * 1000),
        )

    async def _responder(self, pergunta: str, contexto: Contexto, andamento: Andamento) -> dict:
        uso = andamento.uso
        padrao = _periodo_padrao(contexto)
        instrucoes = instrucoes_do_plano(contexto, padrao)
        execucao = await self.planejador.run(
            pergunta_delimitada(pergunta), instructions=instrucoes, usage=uso
        )
        # Sem consulta, o "não sei" só pode citar anos: os da pergunta, do período e da base.
        anos = [*_anos_citados(pergunta), *_anos(padrao, padrao, contexto)]
        for tentativa in range(TENTATIVAS_SQL):
            plano = execucao.output
            alternativa = _sem_numero_inventado(plano.alternativa, anos)
            if plano.tipo != 'consulta':
                return _nao_sei(
                    _sem_numero_inventado(plano.motivo, anos) or MOTIVO_SEM_DADO, alternativa
                )
            consulta = await self._executar(plano.sql, andamento)
            if consulta.erro is None:
                break
            if tentativa + 1 == TENTATIVAS_SQL:
                return _nao_sei(
                    'Não consegui montar uma consulta válida para a pergunta.', alternativa
                )
            execucao = await self.planejador.run(
                pedido_de_correcao(consulta.erro),
                message_history=execucao.all_messages(),
                instructions=instrucoes,
                usage=uso,
            )
        periodo = _periodo(plano, padrao, consulta)
        usados = dict(
            metrica=plano.metrica, filtros=plano.filtros, periodo=periodo and _usado(periodo)
        )
        # Uma agregação sobre zero linhas devolve uma linha só de nulos: também é "sem dado".
        if not any(valor is not None for linha in consulta.linhas for valor in linha):
            onde = f' em {periodo.descricao}' if periodo else ''
            return _nao_sei(
                f'A consulta não encontrou dados de {plano.metrica}{onde}.', alternativa, **usados
            )
        try:
            redacao = await self.redator.run(
                pedido_de_redacao(pergunta, plano.metrica, plano.filtros, periodo, consulta),
                usage=uso,
            )
        except UnexpectedModelBehavior:
            return _nao_sei(
                'O modelo não redigiu a resposta no formato esperado.', alternativa, **usados
            )
        texto = redacao.output.strip()
        if not texto:
            return _nao_sei('O modelo não redigiu a resposta.', alternativa, **usados)
        permitidos = [len(consulta.linhas), *_anos_citados(pergunta)]
        # No corte da guarda, o total é só o limite: "há 1.000 UCs" não se sustenta.
        if consulta.total_linhas < LIMITE_MAXIMO:
            permitidos.append(consulta.total_linhas)
        if periodo is not None:
            permitidos += [periodo.meses, *_anos(periodo, padrao, contexto)]
        # Só as linhas que o redator viu: as que passam das exibidas não sustentam o texto.
        # Os números da pergunta só valem como limiar ("acima de 30%"), nunca como resultado.
        if sem_lastro := numeros_sem_lastro(
            texto, consulta.linhas, permitidos, numeros_citados(pergunta), consulta.colunas
        ):
            return _nao_sei(
                'A resposta citava números que não estão no resultado da consulta: '
                f'{", ".join(sem_lastro)}.',
                alternativa,
                **usados,
            )
        return dict(tipo='resposta', texto=texto, **usados)

    async def _executar(self, sql: str, andamento: Andamento) -> Consulta:
        """Roda o SQL e já o guarda no andamento, também quando o banco não responde."""
        try:
            seguro = validar_sql(sql, VISOES_POR_NOME)
        except SQLRejeitado as erro:
            consulta = Consulta(sql_gerado=sql, erro=f'SQL rejeitado pela guarda: {erro}')
        else:
            try:
                resultado = await self.executor.executar(seguro)
            except ConsultaFalhou as erro:
                consulta = Consulta(
                    sql_gerado=sql, sql_executado=seguro, erro=f'Erro do banco: {erro}'
                )
            except BancoIndisponivel as erro:
                andamento.consultas.append(
                    Consulta(
                        sql_gerado=sql, sql_executado=seguro, erro=f'Banco indisponível: {erro}'
                    )
                )
                raise
            else:
                consulta = Consulta(
                    sql_gerado=sql,
                    sql_executado=seguro,
                    colunas=resultado.colunas,
                    linhas=resultado.linhas[:LINHAS_EXIBIDAS],
                    total_linhas=len(resultado.linhas),
                    duracao_ms=resultado.duracao_ms,
                )
        andamento.consultas.append(consulta)
        return consulta


def _nao_sei(motivo: str, alternativa: str | None = None, **usados) -> dict:
    texto = f'Não sei. {motivo}'
    return dict(tipo='nao_sei', texto=texto, motivo=motivo, alternativa=alternativa, **usados)


def _periodo_padrao(contexto: Contexto) -> Periodo:
    """Sem período na pergunta, vale o da última troca da conversa, depois o da tela e,
    por fim, os 12 meses até a competência mais recente."""
    anterior = next((t.periodo for t in reversed(contexto.historico) if t.periodo), None)
    if anterior is not None:
        return Periodo(anterior.inicio, anterior.fim)
    return contexto.periodo or periodo_padrao(
        contexto.competencia_mais_recente, contexto.competencia_inicial
    )


def _sem_numero_inventado(texto: str | None, permitidos: list) -> str | None:
    """O texto do modelo, ou None quando ele cita um número que não se sustenta."""
    if texto and numeros_sem_lastro(texto, [], permitidos):
        return None
    return texto


def _periodo(plano: Plano, padrao: Periodo, consulta: Consulta) -> Periodo | None:
    """O período declarado na resposta. Sem período no plano, vale o padrão, a não ser que a
    consulta só leia retratos da carga (ucs, fila_inspecao), que não têm eixo de tempo."""
    if plano.periodo_inicio is None and plano.periodo_fim is None:
        visoes = {
            t.name
            for t in sqlglot.parse_one(consulta.sql_executado, read=DIALETO).find_all(exp.Table)
        }
        lidas = [VISOES_POR_NOME[nome] for nome in visoes if nome in VISOES_POR_NOME]
        if lidas and all(visao.coluna_tempo is None for visao in lidas):
            return None
    inicio = (plano.periodo_inicio or plano.periodo_fim or padrao.inicio).replace(day=1)
    fim = (plano.periodo_fim or plano.periodo_inicio or padrao.fim).replace(day=1)
    return Periodo(min(inicio, fim), max(inicio, fim))


def _usado(periodo: Periodo) -> PeriodoUsado:
    return PeriodoUsado(inicio=periodo.inicio, fim=periodo.fim, descricao=periodo.descricao)


def _anos_citados(pergunta: str) -> set[int]:
    """Os anos escritos na pergunta: "e em 2024?" deixa a resposta citar 2024."""
    return {
        int(n)
        for n in numeros_citados(pergunta)
        if n == n.to_integral_value() and 1900 <= n <= 2100
    }


def _anos(periodo: Periodo, padrao: Periodo, contexto: Contexto) -> set[int]:
    """Anos que o texto pode citar: os do período e o anterior a ele (comparação ano contra
    ano), os da comparação da tela e o da competência mais recente."""
    anos = set(range(periodo.inicio.year - 1, periodo.fim.year + 1))
    anos |= {padrao.inicio.year, padrao.fim.year, contexto.competencia_mais_recente.year}
    if contexto.comparacao is not None:
        anos |= {contexto.comparacao.inicio.year, contexto.comparacao.fim.year}
    return anos
