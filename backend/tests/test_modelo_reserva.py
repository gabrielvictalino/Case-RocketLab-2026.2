"""Montagem do modelo do agente pela configuração, com e sem o modelo de reserva."""

import pytest
from pydantic import ValidationError
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel

from app.core.config import Settings
from app.modules.assistente.service import modelo_configurado

RESERVA = dict(ai_provedor_reserva='openrouter', ai_modelo_reserva='google/gemini-3.1-flash-lite')


def configuracao(**campos):
    # Sem o .env local: cada teste diz quais chaves existem.
    padrao = dict(
        ai_provedor='google',
        ai_modelo='gemini-3.1-flash-lite',
        ai_provedor_reserva=None,
        ai_modelo_reserva=None,
        gemini_api_key=None,
        openrouter_api_key=None,
    )
    return Settings(_env_file=None, **{**padrao, **campos})


def test_sem_reserva_e_o_modelo_de_sempre():
    modelo = modelo_configurado(configuracao(gemini_api_key='chave-google'))
    assert isinstance(modelo, GoogleModel)
    assert modelo.model_name == 'gemini-3.1-flash-lite'


def test_com_reserva_e_as_duas_chaves_o_principal_vem_primeiro():
    settings = configuracao(
        gemini_api_key='chave-google', openrouter_api_key='chave-openrouter', **RESERVA
    )
    modelo = modelo_configurado(settings)
    assert isinstance(modelo, FallbackModel)
    principal, reserva = modelo.models
    assert isinstance(principal, GoogleModel) and isinstance(reserva, OpenRouterModel)
    assert reserva.model_name == 'google/gemini-3.1-flash-lite'


@pytest.mark.parametrize(
    'chaves, esperado',
    [
        (dict(gemini_api_key='chave-google'), GoogleModel),
        (dict(openrouter_api_key='chave-openrouter'), OpenRouterModel),
        (dict(gemini_api_key='', openrouter_api_key='chave-openrouter'), OpenRouterModel),
    ],
    ids=['so-principal', 'so-reserva', 'principal-vazia'],
)
def test_modelo_sem_chave_fica_de_fora(chaves, esperado):
    assert isinstance(modelo_configurado(configuracao(**chaves, **RESERVA)), esperado)


def test_sem_nenhuma_chave_nao_ha_modelo():
    assert modelo_configurado(configuracao(**RESERVA)) is None


def test_reserva_vazia_do_compose_e_nenhuma():
    settings = configuracao(ai_provedor_reserva='', ai_modelo_reserva='')
    assert settings.ai_provedor_reserva is None and settings.ai_modelo_reserva is None


@pytest.mark.parametrize(
    'campos',
    [dict(ai_provedor_reserva='openrouter'), dict(ai_modelo_reserva='google/gemini')],
    ids=['so-provedor', 'so-modelo'],
)
def test_reserva_pela_metade_e_recusada(campos):
    with pytest.raises(ValidationError, match='juntos'):
        configuracao(**campos)
