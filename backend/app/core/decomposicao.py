from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

DOIS_DECIMAIS = Decimal('0.01')
ZERO = Decimal('0.00')


@dataclass(frozen=True)
class Efeitos:
    volume: Decimal
    reajuste: Decimal
    bandeira: Decimal
    mix: Decimal


def _arredondar(valor: Decimal) -> Decimal:
    return valor.quantize(DOIS_DECIMAIS, rounding=ROUND_HALF_UP)


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
    """Decompõe a variação da receita segundo a fórmula canônica R5 do contrato.

    Em todos os casos, inclusive os de borda, o mix é o resíduo, e os quatro efeitos
    somam exatamente R1 - R0.
    """
    delta_r = r1 - r0

    if q0 == 0 or (t0 + b0) == 0:
        volume, reajuste, bandeira = _arredondar(delta_r), ZERO, ZERO
    elif q1 == 0:
        # Cobrança sem volume no período atual (ex.: taxa mínima): R1 fica no mix.
        volume, reajuste, bandeira = _arredondar(-r0), ZERO, ZERO
    else:
        p0_medio = r0 / q0
        k0 = r0 / (t0 + b0)
        volume = _arredondar((q1 - q0) * p0_medio)
        reajuste = _arredondar(q1 * (t1 / q1 - t0 / q0) * k0)
        bandeira = _arredondar(q1 * (b1 / q1 - b0 / q0) * k0)

    mix = delta_r - volume - reajuste - bandeira
    return Efeitos(volume=volume, reajuste=reajuste, bandeira=bandeira, mix=_arredondar(mix))
