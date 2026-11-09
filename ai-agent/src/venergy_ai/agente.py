"""Agente Text-to-SQL: pergunta → plano → SQL → guarda → execução → resposta.

O fluxo é orquestrado aqui, não pelo modelo: são duas chamadas ao LLM (plano e
redação), mais uma de correção quando o SQL falha. Assim o número de tentativas
é fixo e cada passo pode ser testado com o modelo simulado.
"""

import logging
import time
from datetime import date
from typing import Literal

import pydantic_ai
from pydantic import BaseModel, Field, model_validator
from pydantic_ai import Agent, AgentRunResult, ModelSettings, UnexpectedModelBehavior
from pydantic_ai.models import Model

from venergy_ai.executor import ConsultaFalhou, ExecutorSQL
from venergy_ai.guarda_sql import LIMITE_MAXIMO, SQLRejeitado, conferir_sql
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
    RespostaAgente,
)
from venergy_ai.modelo import FALHAS_DO_PROVEDOR, modelo_que_respondeu, provedor_indisponivel
from venergy_ai.numeros import numeros_citados, numeros_da_pergunta, numeros_sem_lastro
from venergy_ai.semantica import VISOES_POR_NOME, Periodo, periodo_padrao

# O banner do PydanticAI sai na saída padrão na primeira execução: no backend é só ruído.
pydantic_ai.BANNER_ENABLED = False
logger = logging.getLogger(__name__)

# A primeira consulta e no máximo uma nova tentativa.
TENTATIVAS_SQL = 2
CONFIGURACAO = ModelSettings(temperature=0, timeout=20)
# O motivo do "não sei" é texto do modelo: com número que não se sustenta, sai este.
MOTIVO_SEM_DADO = 'Os dados disponíveis não respondem a essa pergunta.'
# Como uma consulta consta no andamento enquanto roda: se o teto de tempo a cancelar, a
# auditoria fica com o SQL e com este erro.
CONSULTA_INTERROMPIDA = 'Consulta interrompida antes de terminar.'


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
        except FALHAS_DO_PROVEDOR as erro:
            raise provedor_indisponivel(erro) from erro
        except UnexpectedModelBehavior:
            campos = _nao_sei('O modelo não devolveu a resposta no formato esperado.')
        return RespostaAgente(
            **campos,
            consultas=andamento.consultas,
            modelo=andamento.modelo,
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
        self._anotar_modelo(andamento, execucao)
        # Sem consulta, o "não sei" só pode citar os anos (da pergunta, do período e da base)
        # e os números que a pergunta usa como limiar, seleção ou período, no mesmo papel.
        anos = [*_anos_citados(pergunta), *_anos(padrao, padrao, contexto)]
        da_pergunta = numeros_da_pergunta(pergunta)
        for tentativa in range(TENTATIVAS_SQL):
            plano = execucao.output
            alternativa = _sem_numero_inventado(
                plano.alternativa, anos, da_pergunta, 'a alternativa do "não sei"'
            )
            if plano.tipo != 'consulta':
                motivo = _sem_numero_inventado(
                    plano.motivo, anos, da_pergunta, 'o motivo do "não sei"'
                )
                return _nao_sei(motivo or MOTIVO_SEM_DADO, alternativa)
            consulta, views = await self._executar(plano.sql, andamento)
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
            self._anotar_modelo(andamento, execucao)
        periodo = _periodo(plano, padrao, views)
        # A métrica e os filtros também são texto do modelo e vão para a tela: um número
        # deles precisa estar no SQL que rodou, ou ser um ano, um número da pergunta, os
        # meses do período ("últimos 12 meses", que o SQL filtra por datas) ou o número de
        # linhas do resultado.
        meses = [periodo.meses] if periodo else []
        do_sql = [*anos, *meses, len(consulta.linhas), *numeros_citados(consulta.sql_executado)]
        metrica = _sem_numero_inventado(plano.metrica, do_sql, da_pergunta, 'a métrica')
        filtros = [
            filtro
            for filtro in plano.filtros
            if _sem_numero_inventado(filtro, do_sql, da_pergunta, 'um filtro')
        ]
        usados = dict(metrica=metrica, filtros=filtros, periodo=periodo and _usado(periodo))
        # Uma agregação sobre zero linhas devolve uma linha só de nulos: também é "sem dado".
        if not any(valor is not None for linha in consulta.linhas for valor in linha):
            onde = f' em {periodo.descricao}' if periodo else ''
            de_que = f' de {metrica}' if metrica else ''
            return _nao_sei(f'A consulta não encontrou dados{de_que}{onde}.', alternativa, **usados)
        try:
            redacao = await self.redator.run(
                # A métrica e os filtros já conferidos: um número descartado não volta pelo
                # texto do redator.
                pedido_de_redacao(pergunta, metrica, filtros, periodo, consulta),
                usage=uso,
            )
        except UnexpectedModelBehavior:
            return _nao_sei(
                'O modelo não redigiu a resposta no formato esperado.', alternativa, **usados
            )
        self._anotar_modelo(andamento, redacao)
        texto = redacao.output.strip()
        if not texto:
            return _nao_sei('O modelo não redigiu a resposta.', alternativa, **usados)
        if sem_lastro := conferir_numeros(texto, pergunta, consulta, periodo, padrao, contexto):
            return _nao_sei(
                'A resposta citava números que não estão no resultado da consulta: '
                f'{", ".join(sem_lastro)}.',
                alternativa,
                **usados,
            )
        return dict(tipo='resposta', texto=texto, **usados)

    def _anotar_modelo(self, andamento: Andamento, execucao: AgentRunResult) -> None:
        """Troca o nome da configuração pelo do modelo que respondeu. Com reserva, o plano e a
        redação podem vir de modelos diferentes: a auditoria guarda os dois, em ordem."""
        nome = modelo_que_respondeu(execucao, self.modelo)
        if andamento.modelo in (None, self.modelo.model_name):
            andamento.modelo = nome
        elif nome not in andamento.modelo.split(', '):
            andamento.modelo = f'{andamento.modelo}, {nome}'

    async def _executar(self, sql: str, andamento: Andamento) -> tuple[Consulta, frozenset[str]]:
        """Roda o SQL e devolve a consulta e as views que ela lê.

        O SQL entra no andamento antes de rodar: se o teto de tempo cancelar a pergunta no
        meio da consulta, ou o banco não responder, a auditoria fica com ele."""
        try:
            conferido = conferir_sql(sql, VISOES_POR_NOME)
        except SQLRejeitado as erro:
            consulta = Consulta(sql_gerado=sql, erro=f'SQL rejeitado pela guarda: {erro}')
            andamento.consultas.append(consulta)
            return consulta, frozenset()
        seguro = conferido.sql
        indice = len(andamento.consultas)
        andamento.consultas.append(
            Consulta(sql_gerado=sql, sql_executado=seguro, erro=CONSULTA_INTERROMPIDA)
        )
        try:
            resultado = await self.executor.executar(seguro)
        except ConsultaFalhou as erro:
            consulta = Consulta(sql_gerado=sql, sql_executado=seguro, erro=f'Erro do banco: {erro}')
        except BancoIndisponivel as erro:
            andamento.consultas[indice] = Consulta(
                sql_gerado=sql, sql_executado=seguro, erro=f'Banco indisponível: {erro}'
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
        andamento.consultas[indice] = consulta
        return consulta, conferido.views


def _nao_sei(motivo: str, alternativa: str | None = None, **usados) -> dict:
    texto = f'Não sei. {motivo}'
    return dict(tipo='nao_sei', texto=texto, motivo=motivo, alternativa=alternativa, **usados)


def _periodo_padrao(contexto: Contexto) -> Periodo:
    """Sem período na pergunta, vale o da última troca da conversa, depois o da tela e,
    por fim, os 12 meses até a competência mais recente.

    Se a tela mudou de período depois da última troca, a tela vence: a analista que troca
    2025 por 2024 e faz uma pergunta nova quer 2024, com a comparação da tela."""
    anterior = next((t for t in reversed(contexto.historico) if t.periodo), None)
    if anterior is not None and anterior.periodo_da_tela == contexto.periodo:
        return Periodo(anterior.periodo.inicio, anterior.periodo.fim)
    return contexto.periodo or periodo_padrao(
        contexto.competencia_mais_recente, contexto.competencia_inicial
    )


def _sem_numero_inventado(
    texto: str | None, permitidos: list, da_pergunta: list, o_que: str
) -> str | None:
    """O texto do modelo, ou None quando ele cita um número que não se sustenta.

    `permitidos` valem em qualquer lugar; `da_pergunta`, só no papel que tinham nela
    ("as 5 UCs", "acima de 30%")."""
    if texto and numeros_sem_lastro(texto, [], permitidos, da_pergunta):
        # Só o campo: o texto pode trazer dados da consulta.
        logger.info('Descartado o texto do modelo em %s: cita número sem lastro.', o_que)
        return None
    return texto


def _periodo(plano: Plano, padrao: Periodo, views: frozenset[str]) -> Periodo | None:
    """O período declarado na resposta. Sem período no plano, vale o padrão, a não ser que a
    consulta só leia retratos da carga (ucs, fila_inspecao), que não têm eixo de tempo.
    `views` são as que a guarda viu no SQL."""
    if plano.periodo_inicio is None and plano.periodo_fim is None:
        lidas = [VISOES_POR_NOME[nome] for nome in views if nome in VISOES_POR_NOME]
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


def conferir_numeros(
    texto: str,
    pergunta: str,
    consulta: Consulta,
    periodo: Periodo | None,
    padrao: Periodo,
    contexto: Contexto,
) -> list[str]:
    """Os números do texto que não se sustentam.

    Valem as linhas que o redator viu, as contagens de linhas (menos o total no corte da
    guarda), os anos da pergunta e, com período, o número de meses e os anos dele. Os
    demais números da pergunta só valem no papel que tinham nela: limiar ("acima de
    30%", "3 ou mais"), seleção ("os 10 bairros") ou período ("últimos 3 anos").
    `padrao` é o período padrão que o plano recebeu."""
    return numeros_sem_lastro(
        texto,
        consulta.linhas,
        numeros_permitidos(pergunta, consulta, periodo, padrao, contexto),
        numeros_da_pergunta(pergunta),
        consulta.colunas,
    )


def numeros_permitidos(
    pergunta: str,
    consulta: Consulta,
    periodo: Periodo | None,
    padrao: Periodo,
    contexto: Contexto,
) -> list[int]:
    """Números que o texto pode citar em qualquer lugar, sem estar nas linhas."""
    permitidos = [len(consulta.linhas), *_anos_citados(pergunta)]
    # No corte da guarda, o total é só o limite: "há 1.000 UCs" não se sustenta.
    if consulta.total_linhas < LIMITE_MAXIMO:
        permitidos.append(consulta.total_linhas)
    if periodo is not None:
        permitidos += [periodo.meses, *_anos(periodo, padrao, contexto)]
    return permitidos


def _anos(periodo: Periodo, padrao: Periodo, contexto: Contexto) -> set[int]:
    """Anos que o texto pode citar: os do período e o anterior a ele (comparação ano contra
    ano), os da comparação da tela, o da competência mais recente e o primeiro da base
    ("a base começa em 2022")."""
    anos = set(range(periodo.inicio.year - 1, periodo.fim.year + 1))
    anos |= {padrao.inicio.year, padrao.fim.year, contexto.competencia_mais_recente.year}
    if contexto.competencia_inicial is not None:
        anos.add(contexto.competencia_inicial.year)
    if contexto.comparacao is not None:
        anos |= {contexto.comparacao.inicio.year, contexto.comparacao.fim.year}
    return anos
