from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

DOIS_DECIMAIS = Decimal('0.01')


@dataclass(frozen=True)
class Efeitos:
    volume: Decimal
    reajuste: Decimal
    bandeira: Decimal
    mix: Decimal


def decompor(
    q0: Decimal,
    r0: Decimal,
    t0: Decimal,
    b0: Decimal,
    q1: Decimal,
    r1: Decimal,
    t1: Decimal,
    b1: Decimal,
) -> Efeitos:
    """Decompõe a variação da receita segundo a fórmula canônica R5 do contrato."""
    delta_r = r1 - r0
    zero = Decimal('0.00')

    if q0 == 0 or (t0 + b0) == 0:
        return Efeitos(
            volume=delta_r.quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP),
            reajuste=zero,
            bandeira=zero,
            mix=zero,
        )

    if q1 == 0:
        return Efeitos(
            volume=(-r0).quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP),
            reajuste=zero,
            bandeira=zero,
            mix=zero,
        )

    p0_medio = r0 / q0
    t0_unit = t0 / q0
    t1_unit = t1 / q1
    b0_unit = b0 / q0
    b1_unit = b1 / q1
    k0 = r0 / (t0 + b0)

    volume = ((q1 - q0) * p0_medio).quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP)
    reajuste = (q1 * (t1_unit - t0_unit) * k0).quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP)
    bandeira = (q1 * (b1_unit - b0_unit) * k0).quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP)
    mix = delta_r - volume - reajuste - bandeira

    return Efeitos(
        volume=volume,
        reajuste=reajuste,
        bandeira=bandeira,
        mix=mix.quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP),
    )
