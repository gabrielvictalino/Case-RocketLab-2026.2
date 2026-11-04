from datetime import date, timedelta

import pytest

from app.core.errors import APIError
from app.core.periodos import Periodo, validar_periodos
from app.modules.perdas.schemas import Resultado


@pytest.mark.parametrize(
    'value',
    [
        '2025-13..2026-01',
        '2025-2..2025-03',
        '2025-05..2025-04',
        '0000-01..2025-01',
        '2025-01',
        '2025-01..2025-02junk',
    ],
)
def test_invalid_period(value):
    with pytest.raises(APIError) as error:
        Periodo.parse(value)
    assert error.value.status_code == 422


def test_default_comparison_and_bounds():
    atual, anterior = validar_periodos('2025-07..2026-06', None, date(2022, 7, 1), date(2026, 6, 1))
    assert atual.fim == date(2026, 6, 1)
    assert anterior == Periodo(date(2024, 7, 1), date(2025, 6, 1))
    atual, anterior = validar_periodos('2022-07..2023-06', None, date(2022, 7, 1), date(2026, 6, 1))
    assert atual.inicio == date(2022, 7, 1)
    assert anterior is None
    with pytest.raises(APIError):
        validar_periodos('2022-07..2023-06', '2021-07..2022-06', date(2022, 7, 1), date(2026, 6, 1))


def test_future_inspection_date_rejected():
    with pytest.raises(ValueError, match='futura'):
        Resultado(
            resultado='SEM IRREGULARIDADE', kwh_recuperado=0, data=date.today() + timedelta(days=1)
        )
    assert (
        Resultado(resultado='SEM IRREGULARIDADE', kwh_recuperado=0, data=date.today()).data
        == date.today()
    )


@pytest.mark.parametrize(
    'result,tipo,kwh',
    [
        ('IRREGULARIDADE CONFIRMADA', None, 10),
        ('IRREGULARIDADE CONFIRMADA', 'DESVIO', 0),
        ('SEM IRREGULARIDADE', None, 1),
        ('SEM IRREGULARIDADE', 'DESVIO', 0),
        ('SEM IRREGULARIDADE', None, -1),
        ('SEM IRREGULARIDADE', None, 'NaN'),
    ],
)
def test_invalid_result(result, tipo, kwh):
    with pytest.raises(ValueError):
        Resultado(resultado=result, tipo_irregularidade=tipo, kwh_recuperado=kwh, data='2026-06-01')
