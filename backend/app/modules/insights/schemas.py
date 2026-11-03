from datetime import datetime
from typing import Literal

from venergy_ai.interface import Observacao

from app.modules.metricas import RespostaMetricas

# Slug da rota → nome que o modelo recebe.
TELAS = {'visao-geral': 'Visão Geral', 'receita': 'Receita'}
Tela = Literal['visao-geral', 'receita']


class Insight(RespostaMetricas):
    tela: Tela
    observacoes: list[Observacao]
    modelo: str
    gerado_em: datetime
