"""Avaliação do agente com o modelo real. Fica fora do `pytest` padrão e do CI obrigatório.

Roda pelo workflow "Avaliação do agente" (manual e semanal) ou localmente, com Docker:

    GEMINI_API_KEY=... uv run pytest ai-agent/evals

Sem a chave, o teste é pulado. O relatório sai em `ai-agent/evals/relatorio.md` e, no
GitHub Actions, também no resumo da execução.
"""

import asyncio
import os
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from venergy_ai.agente import AgenteTextoSQL
from venergy_ai.avaliacao import avaliar, carregar, relatorio, taxa_de_acerto
from venergy_ai.executor import ExecutorAiRead
from venergy_ai.modelo import MODELO_PADRAO, criar_modelo

pytestmark = [pytest.mark.integration, pytest.mark.avaliacao]

PASTA = Path(__file__).parent
CHAVES = {'google': 'GEMINI_API_KEY', 'openrouter': 'OPENROUTER_API_KEY'}


class AgenteComPausa:
    """Espaça as perguntas para não passar do limite por minuto do provedor."""

    def __init__(self, agente, pausa_s):
        self.agente, self.pausa_s = agente, pausa_s

    async def responder(self, pergunta, contexto, andamento=None):
        await asyncio.sleep(self.pausa_s)
        return await self.agente.responder(pergunta, contexto, andamento)


@pytest.fixture(scope='module')
def modelo():
    provedor = os.environ.get('AI_PROVEDOR', 'google')
    chave = os.environ.get(CHAVES[provedor])
    if not chave:
        pytest.skip(f'Defina {CHAVES[provedor]} para avaliar o agente com o modelo real.')
    return criar_modelo(provedor, os.environ.get('AI_MODELO') or MODELO_PADRAO, chave)


async def test_avaliacao_do_agente(infrastructure, modelo):
    engine = create_async_engine(
        infrastructure['settings'].database_url_ai, connect_args={'command_timeout': 10}
    )
    try:
        executor = ExecutorAiRead(engine)
        [[recente]] = (
            await executor.executar('SELECT max(competencia) FROM receita_volume_mensal')
        ).linhas
        agente = AgenteComPausa(
            AgenteTextoSQL(modelo, executor), float(os.environ.get('AVALIACAO_PAUSA_S', '4'))
        )
        casos = carregar(PASTA / 'perguntas.yaml')
        resultados = await avaliar(agente, executor, casos, date.fromisoformat(recente))
    finally:
        await engine.dispose()
    texto = relatorio(resultados, modelo.model_name)
    (PASTA / 'relatorio.md').write_text(texto, encoding='utf-8')
    if resumo := os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(resumo, 'a', encoding='utf-8') as arquivo:
            arquivo.write(texto)
    print(texto)
    minimo = float(os.environ.get('AVALIACAO_MINIMO', '0.7'))
    assert taxa_de_acerto(resultados) >= minimo, f'Taxa de acerto abaixo de {minimo:.0%}.'
