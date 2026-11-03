"""Fronteira entre o agente e o backend: o que entra numa pergunta e o que sai na resposta.

O backend só conhece estes tipos. Ele monta o `Contexto` a partir da tela e da carga
publicada, e grava a `RespostaAgente` na auditoria pela conexão do portal, que o
agente nunca recebe. Nos insights, ele monta o `PedidoInsight` com os números da tela
e recebe o `Insight` com as observações já validadas.
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field
from pydantic_ai import RunUsage

from venergy_ai.semantica.periodo import Periodo

LINHAS_EXIBIDAS = 50
# Trocas anteriores que o agente recebe num follow-up.
TROCAS_NA_CONVERSA = 5


class PeriodoUsado(BaseModel):
    inicio: date
    fim: date
    descricao: str


class Troca(BaseModel):
    """Uma pergunta já respondida na conversa: o estado que um follow-up herda."""

    pergunta: str
    metrica: str | None = None
    filtros: list[str] = Field(default_factory=list)
    periodo: PeriodoUsado | None = None
    sql: str | None = None


class Contexto(BaseModel):
    """O que a tela e a conversa sabem quando a pergunta é feita."""

    competencia_mais_recente: date
    # Primeira competência da carga: a cobertura da base vai para o prompt.
    competencia_inicial: date | None = None
    # Data do instantâneo financeiro do manifesto: separa a conta atrasada da em aberto.
    data_referencia: date | None = None
    tela: str | None = None
    # Período e comparação da tela: o padrão quando a pergunta não define período.
    periodo: Periodo | None = None
    comparacao: Periodo | None = None
    recortes: dict[str, str] = Field(default_factory=dict)
    # Últimas trocas da conversa, da mais antiga para a mais recente.
    historico: list[Troca] = Field(default_factory=list, max_length=TROCAS_NA_CONVERSA)


class Consulta(BaseModel):
    """Uma tentativa: o SQL que o modelo escreveu e o que de fato rodou."""

    sql_gerado: str
    # Nulo quando a guarda rejeitou o SQL e nada foi executado.
    sql_executado: str | None = None
    colunas: list[str] = Field(default_factory=list)
    linhas: list[list[Any]] = Field(
        default_factory=list, description=f'Até {LINHAS_EXIBIDAS} linhas, para exibição.'
    )
    total_linhas: int = 0
    duracao_ms: int | None = None
    erro: str | None = None


class RespostaAgente(BaseModel):
    tipo: Literal['resposta', 'nao_sei']
    texto: str
    metrica: str | None = None
    filtros: list[str] = Field(default_factory=list)
    periodo: PeriodoUsado | None = None
    # Preenchidos no "não sei": por que não respondeu e o que os dados permitem.
    motivo: str | None = None
    alternativa: str | None = None
    consultas: list[Consulta] = Field(default_factory=list)
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0


@dataclass
class Andamento:
    """O que o agente já fez numa pergunta, preenchido enquanto ele trabalha.

    Quem chama lê o andamento também quando a pergunta falha ou é cancelada por tempo:
    assim a auditoria guarda o SQL que já rodou e os tokens já gastos.
    """

    modelo: str | None = None
    consultas: list[Consulta] = field(default_factory=list)
    uso: RunUsage = field(default_factory=RunUsage)

    @property
    def tokens_entrada(self) -> int:
        return self.uso.input_tokens

    @property
    def tokens_saida(self) -> int:
        return self.uso.output_tokens


CampoDoFato = Literal['valor', 'comparacao', 'variacao', 'variacao_pct']


class Fato(BaseModel):
    """Um número que a tela mostra, calculado pelo backend com os serviços dela."""

    # Identifica o fato no pedido: "receita", "efeito_bandeira", "local:Recife".
    chave: str
    # A etiqueta mostrada ao lado da observação: "Receita faturada", "Efeito bandeira".
    metrica: str
    # "R$", "kWh", "%", "R$/kWh", "h por UC". A variação de um fato em % está em pp.
    unidade: str
    valor: Decimal | None = None
    comparacao: Decimal | None = None
    variacao: Decimal | None = None
    variacao_pct: Decimal | None = None


class PedidoInsight(BaseModel):
    tela: str
    periodo: Periodo
    comparacao: Periodo | None = None
    recortes: dict[str, str] = Field(default_factory=dict)
    fatos: list[Fato]


class ValorCitado(BaseModel):
    """Um número da observação e o valor do fato que o sustenta."""

    # Como o número está escrito no texto: "5,3%", "R$ 1,2 milhão" sem o "R$".
    trecho: str
    # Onde o trecho está no texto da observação: o frontend destaca pela posição.
    inicio: int
    fim: int
    chave: str
    metrica: str
    campo: CampoDoFato
    valor: Decimal
    unidade: str


class Observacao(BaseModel):
    chave: str
    metrica: str
    texto: str
    valores: list[ValorCitado]


class Insight(BaseModel):
    observacoes: list[Observacao]
    # Por que cada observação descartada saiu: número sem lastro, chave desconhecida...
    descartadas: list[str] = Field(default_factory=list)
    modelo: str
    tokens_entrada: int = 0
    tokens_saida: int = 0
    latencia_ms: int = 0


class ProvedorIndisponivel(RuntimeError):
    """O provedor do modelo falhou (rede, autenticação, cota ou erro do servidor)."""


class BancoIndisponivel(RuntimeError):
    """O Postgres da role `ai_read` não respondeu. Não é erro do SQL: não há o que corrigir."""


class InsightIndisponivel(RuntimeError):
    """O modelo não redigiu nenhuma observação que passe na validação."""


class Assistente(Protocol):
    async def responder(
        self, pergunta: str, contexto: Contexto, andamento: Andamento | None = None
    ) -> RespostaAgente: ...


class Redator(Protocol):
    # Identifica o modelo e as instruções: um insight guardado com outra versão não vale.
    versao: str

    async def redigir(self, pedido: PedidoInsight, uso: RunUsage | None = None) -> Insight: ...
