from datetime import datetime
from typing import Literal

from venergy_ai.interface import Observacao

from app.modules.assistente.schemas import TELAS as TELAS_DO_PORTAL
from app.modules.metricas import RespostaMetricas

Tela = Literal['visao-geral', 'receita']
# Slug da rota → nome que o modelo recebe, o mesmo que o assistente usa.
TELAS = {tela: TELAS_DO_PORTAL[tela] for tela in Tela.__args__}


class Insight(RespostaMetricas):
    tela: Tela
    observacoes: list[Observacao]
    modelo: str
    gerado_em: datetime
