"""Insights: o modelo só redige observações sobre os números que a tela já mostra.

O backend calcula os fatos com os serviços da tela e os manda aqui. O modelo devolve
de 3 a 5 observações, cada uma ligada a um fato. Cada número do texto precisa estar nos
fatos, com as mesmas regras da resposta do agente (`numeros`). A observação com um
número sem lastro é descartada; sem nenhuma observação válida, o insight fica
indisponível.
"""

import time

import pydantic_ai
from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelAPIError, ModelSettings, RunUsage, UnexpectedModelBehavior
from pydantic_ai.models import Model

from venergy_ai.instrucoes import INSTRUCOES_INSIGHT, pedido_de_insight
from venergy_ai.interface import (
    CampoDoFato,
    Fato,
    Insight,
    InsightIndisponivel,
    Observacao,
    PedidoInsight,
    ProvedorIndisponivel,
    ValorCitado,
)
from venergy_ai.numeros import Citacao, citacoes, numeros_citados
from venergy_ai.semantica.periodo import Periodo

pydantic_ai.BANNER_ENABLED = False

OBSERVACOES = 5
CAMPOS: tuple[CampoDoFato, ...] = ('valor', 'comparacao', 'variacao', 'variacao_pct')
CONFIGURACAO = ModelSettings(temperature=0, timeout=20)

Alvo = tuple[Fato, CampoDoFato, object]


class Rascunho(BaseModel):
    chave: str = Field(description='A chave do fato principal, exatamente como nos fatos.')
    texto: str = Field(description='A observação, com os números escritos a partir dos fatos.')


class Rascunhos(BaseModel):
    observacoes: list[Rascunho] = Field(description='De 3 a 5 observações.')


class RedatorDeInsights:
    """Implementa `Redator`. Só recebe o modelo: os fatos chegam prontos do backend."""

    def __init__(self, modelo: Model):
        self.modelo = modelo
        self.agente = Agent(
            modelo,
            output_type=Rascunhos,
            instructions=INSTRUCOES_INSIGHT,
            model_settings=CONFIGURACAO,
            retries=1,
        )

    async def redigir(self, pedido: PedidoInsight, uso: RunUsage | None = None) -> Insight:
        """`uso` é preenchido também quando o insight falha: quem chama conta os tokens."""
        inicio = time.monotonic()
        uso = RunUsage() if uso is None else uso
        try:
            execucao = await self.agente.run(pedido_de_insight(pedido), usage=uso)
        except ModelAPIError as erro:
            raise ProvedorIndisponivel(str(erro)) from erro
        except UnexpectedModelBehavior as erro:
            raise InsightIndisponivel(
                'O modelo não devolveu as observações no formato esperado.'
            ) from erro
        observacoes, descartadas = validar(execucao.output.observacoes, pedido)
        if not observacoes:
            motivo = '; '.join(descartadas) or 'o modelo não redigiu nenhuma observação'
            raise InsightIndisponivel(f'Nenhuma observação passou na validação: {motivo}.')
        return Insight(
            observacoes=observacoes[:OBSERVACOES],
            descartadas=descartadas,
            modelo=self.modelo.model_name,
            tokens_entrada=uso.input_tokens,
            tokens_saida=uso.output_tokens,
            latencia_ms=round((time.monotonic() - inicio) * 1000),
        )


def validar(rascunhos: list[Rascunho], pedido: PedidoInsight) -> tuple[list[Observacao], list[str]]:
    """Mantém as observações cujos números estão todos nos fatos e diz por que as outras
    saíram. Cada número mantido volta com o valor do fato que o sustenta."""
    fatos = {fato.chave: fato for fato in pedido.fatos}
    alvos: list[Alvo] = [
        (fato, campo, getattr(fato, campo))
        for fato in pedido.fatos
        for campo in CAMPOS
        if getattr(fato, campo) is not None
    ]
    permitidos = _permitidos(pedido)
    observacoes, descartadas, textos = [], [], set()
    for n, rascunho in enumerate(rascunhos, 1):
        texto = rascunho.texto.strip()
        principal = fatos.get(rascunho.chave)
        if principal is None:
            descartadas.append(f'{n}ª com chave desconhecida')
            continue
        if not texto or texto in textos:
            descartadas.append(f'{n}ª vazia ou repetida')
            continue
        citadas = citacoes(texto, [valor for _, _, valor in alvos], permitidos)
        if sem_lastro := [citada.trecho for citada in citadas if not citada.lastros]:
            descartadas.append(f'{n}ª com número fora dos fatos ({", ".join(sem_lastro)})')
            continue
        if not citadas:
            descartadas.append(f'{n}ª sem número dos fatos')
            continue
        textos.add(texto)
        observacoes.append(
            Observacao(
                chave=principal.chave,
                metrica=principal.metrica,
                texto=texto,
                valores=[_valor_citado(citada, alvos, principal) for citada in citadas],
            )
        )
    return observacoes, descartadas


def _valor_citado(citada: Citacao, alvos: list[Alvo], principal: Fato) -> ValorCitado:
    # Um número pode bater com mais de um fato; o da própria observação vem primeiro.
    indice = next(
        (i for i in citada.lastros if alvos[i][0].chave == principal.chave), citada.lastros[0]
    )
    fato, campo, valor = alvos[indice]
    return ValorCitado(
        trecho=citada.trecho,
        chave=fato.chave,
        metrica=fato.metrica,
        campo=campo,
        valor=valor,
        unidade=_unidade(fato, campo),
    )


def _unidade(fato: Fato, campo: CampoDoFato) -> str:
    if campo == 'variacao_pct':
        return '%'
    if campo == 'variacao' and fato.unidade == '%':
        return 'pp'
    return fato.unidade


def _permitidos(pedido: PedidoInsight) -> list[object]:
    """O texto pode citar os anos e o número de meses do período e da comparação, e os
    números que fazem parte de um nome: "Setor 2" num local ou num recorte."""
    periodos = [p for p in (pedido.periodo, pedido.comparacao) if p is not None]
    anos = {ano for p in periodos for ano in (p.inicio.year, p.fim.year)}
    nomes = [fato.metrica for fato in pedido.fatos] + list(pedido.recortes.values())
    return [
        *anos,
        *{_meses(p) for p in periodos},
        *(n for nome in nomes for n in numeros_citados(nome)),
    ]


def _meses(periodo: Periodo) -> int:
    return (
        (periodo.fim.year - periodo.inicio.year) * 12 + periodo.fim.month - periodo.inicio.month + 1
    )
