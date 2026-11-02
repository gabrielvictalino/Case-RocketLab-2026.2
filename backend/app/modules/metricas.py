"""Contexto das métricas: períodos, recortes e metadados da carga publicada."""

from dataclasses import dataclass

from pydantic import BaseModel

from app.core.periodos import Periodo, validar_periodos
from app.modules.meta.schemas import Carga
from app.modules.meta.service import carga


class Recorte(BaseModel):
    municipio: str | None = None
    bairro: str | None = None
    classe: str | None = None
    alimentador: str | None = None

    def condicoes(self, alias: str) -> str:
        # Nomes vêm do schema; todos os valores são parâmetros SQL.
        return ''.join(f' AND {alias}.{key} = :{key}' for key in self.parametros())

    def parametros(self):
        return self.model_dump(exclude_none=True)


class RespostaMetricas(BaseModel):
    periodo: str
    comparacao: str | None
    carga: Carga


@dataclass(frozen=True)
class Contexto:
    atual: Periodo
    anterior: Periodo | None
    carga: Carga

    def metadados(self):
        def formato(p):
            return f'{p.inicio:%Y-%m}..{p.fim:%Y-%m}' if p else None

        return dict(
            periodo=formato(self.atual), comparacao=formato(self.anterior), carga=self.carga
        )


async def contexto(db, periodo: str, comparacao: str | None):
    atual = await carga(db)
    p, c = validar_periodos(
        periodo, comparacao, atual.competencia_inicial, atual.competencia_mais_recente
    )
    return Contexto(p, c, atual)
