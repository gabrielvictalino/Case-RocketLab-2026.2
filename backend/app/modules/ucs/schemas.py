from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.modules.perdas.schemas import Ordem


class MedidorAtual(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_medidor: str
    tipo_medidor: str
    data_instalacao: date


class GD(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    potencia_kw: Decimal
    data_conexao: date


class Cabecalho(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    titular: str
    documento: str
    classe: str
    endereco: str
    municipio: str
    bairro: str
    alimentador: str
    medidor_atual: MedidorAtual | None
    gd: GD | None


class PontoConsumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competencia: date
    consumo_kwh: Decimal
    leitura_estimada: bool
    troca_medidor: bool
    consumo_ajustado: bool


class MesConsumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competencia: date
    atual: PontoConsumo | None
    anterior: PontoConsumo | None


class Consumo(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competencia_inicial: date
    competencia_final: date
    meses: list[MesConsumo]


class FaturaAberta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_fatura: str
    competencia: date
    valor_total: Decimal
    data_vencimento: date
    bandeira: str
    dias_atraso: int | None


class OcorrenciaUC(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_ocorrencia: str
    data_abertura: datetime
    data_encerramento: datetime | None
    duracao_min: Decimal
    duracao_efetiva_min: Decimal
    causa: str
    flag_sobreposicao: bool


class ResumoAlimentador(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    alimentador: str
    interrupcoes: int
    dec: Decimal


class Interrupcoes(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    ocorrencias: list[OcorrenciaUC]
    alimentador: ResumoAlimentador


class ChamadoHistorico(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    sequencia: int
    data: datetime
    descricao: str


class Chamado(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    protocolo: str
    aberto_em: datetime
    assunto: str
    status: str
    nota: int | None
    historico: list[ChamadoHistorico]


class Inspecao(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_inspecao: str
    data: date
    inspetor: str
    resultado: str
    tipo_irregularidade: str | None
    kwh_recuperado: Decimal
    origem: str


class FaturaComparada(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    competencia: date
    id_fatura: str
    volume_faturado_kwh: Decimal
    valor_total: Decimal
    tarifa_base: Decimal
    adicional_bandeira: Decimal
    bandeira: str
    leitura_estimada: bool
    troca_medidor: bool


class EfeitosConta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    consumo: Decimal
    tarifa: Decimal
    bandeira: Decimal
    outros: Decimal


class ExplicacaoConta(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    situacao: Literal['COMPARADA', 'SEM_BASE', 'SEM_FATURA']
    frase: str
    atual: FaturaComparada | None
    anterior: FaturaComparada | None
    variacao_valor: Decimal | None
    variacao_valor_pct: Decimal | None
    variacao_consumo_pct: Decimal | None
    efeitos: EfeitosConta | None


class VisaoUC(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id_uc: str
    data_referencia: date | None
    cabecalho: Cabecalho
    consumo: Consumo
    faturas_abertas: list[FaturaAberta]
    interrupcoes: Interrupcoes
    chamados: list[Chamado]
    inspecoes: list[Inspecao]
    ordem_ativa: Ordem | None
    explicacao_conta: ExplicacaoConta
