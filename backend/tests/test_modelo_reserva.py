"""Montagem do modelo do agente pela configuração, com e sem as reservas."""

import logging

import pytest
from pydantic import ValidationError
from pydantic_ai.models.google import GoogleModel
from pydantic_ai.models.openrouter import OpenRouterModel
from venergy_ai.modelo import ModeloComReserva

from app.core.config import Settings
from app.modules.assistente.service import criar_assistente, modelo_configurado
from app.modules.insights.service import criar_redator

RESERVA = dict(ai_modelos_reserva='openrouter:google/gemini-3.1-flash-lite')


def configuracao(**campos):
    # Sem o .env local: cada teste diz quais chaves existem.
    padrao = dict(
        ai_provedor='google',
        ai_modelo='gemini-3.1-flash-lite',
        ai_modelos_reserva='',
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
    assert isinstance(modelo, ModeloComReserva)
    principal, reserva = modelo.models
    assert isinstance(principal, GoogleModel) and isinstance(reserva, OpenRouterModel)
    assert reserva.model_name == 'google/gemini-3.1-flash-lite'


def test_cadeia_com_varias_reservas_em_ordem():
    settings = configuracao(
        gemini_api_key='chave-google',
        openrouter_api_key='chave-openrouter',
        ai_modelos_reserva=(
            ' openrouter:google/gemini-3.1-flash-lite , google:gemini-outro,'
            'openrouter:meta/llama:free'
        ),
    )
    modelo = modelo_configurado(settings)
    assert [m.model_name for m in modelo.models] == [
        'gemini-3.1-flash-lite',
        'google/gemini-3.1-flash-lite',
        'gemini-outro',
        # Só o primeiro `:` separa o provedor do modelo.
        'meta/llama:free',
    ]


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


def test_modelo_sem_chave_deixa_aviso_no_log(caplog):
    with caplog.at_level(logging.WARNING, logger='venergy.assistente'):
        modelo_configurado(configuracao(gemini_api_key='chave-google', **RESERVA))
    assert 'openrouter:google/gemini-3.1-flash-lite' in caplog.text
    assert 'OPENROUTER_API_KEY' in caplog.text


def test_sem_nenhuma_chave_nao_ha_modelo():
    assert modelo_configurado(configuracao(**RESERVA)) is None


def test_reserva_vazia_do_compose_e_nenhuma():
    assert configuracao(ai_modelos_reserva='').ai_modelos_reserva == []


@pytest.mark.parametrize(
    'reservas, erro',
    [
        ('openrouter', 'provedor:modelo'),
        ('openrouter:', 'provedor:modelo'),
        ('azure:gpt', 'google'),
        ('google:gemini-3.1-flash-lite', 'repete'),
        ('openrouter:x,openrouter:x', 'repete'),
    ],
    ids=['sem-modelo', 'modelo-vazio', 'provedor-desconhecido', 'igual-ao-principal', 'repetida'],
)
def test_reserva_invalida_e_recusada(reservas, erro):
    with pytest.raises(ValidationError, match=erro):
        configuracao(ai_modelos_reserva=reservas)


def test_assistente_e_redator_recebem_o_teto_da_configuracao():
    # Sem o teto, a cadeia não divide o tempo e o teto global cancela antes da última reserva.
    settings = configuracao(
        gemini_api_key='chave-google',
        openrouter_api_key='chave-openrouter',
        assistente_timeout_s=12,
        **RESERVA,
    )
    assert criar_assistente(settings, ai_engine=None).teto_s == 12
    assert criar_redator(settings).teto_s == 12
