import { describe, expect, it } from 'vitest'
import { normalizarIdentificadorUC } from './logicaUnidadeConsumidora'

describe('normalizarIdentificadorUC', () => {
  it.each([
    ['UC100123', 'UC100123'],
    ['uc100123', 'UC100123'],
    ['100123', 'UC100123'],
    [' UC100123 ', 'UC100123'],
    ['000123', 'UC000123'],
  ])('normaliza %s para %s', (entrada, esperado) => {
    expect(normalizarIdentificadorUC(entrada)).toBe(esperado)
  })

  it.each(['', ' ', 'abc123', 'UC', 'UC12A', '12-34'])(
    'rejeita o identificador inválido %s',
    (entrada) => {
      expect(normalizarIdentificadorUC(entrada)).toBeNull()
    },
  )
})
