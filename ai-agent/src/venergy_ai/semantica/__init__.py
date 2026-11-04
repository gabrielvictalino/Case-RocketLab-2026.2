"""Camada semântica do agente: o que cada view de `ai_read` significa e como perguntar a ela."""

from venergy_ai.semantica.catalogo import VISOES, VISOES_POR_NOME, Coluna, Visao
from venergy_ai.semantica.contexto import descrever_periodo_padrao, descrever_semantica
from venergy_ai.semantica.periodo import Periodo, periodo_comparacao, periodo_padrao
from venergy_ai.semantica.vocabulario import LIMITES, VOCABULARIO, Limite, Termo

__all__ = [
    'LIMITES',
    'VISOES',
    'VISOES_POR_NOME',
    'VOCABULARIO',
    'Coluna',
    'Limite',
    'Periodo',
    'Termo',
    'Visao',
    'descrever_periodo_padrao',
    'descrever_semantica',
    'periodo_comparacao',
    'periodo_padrao',
]
