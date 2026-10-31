import { describe, expect, it } from 'vitest'
import { normalizarUc } from '@/features/unidade-consumidora/normalizarUc'

describe('normalizarUc', () => {
  it('aceita UC maiúsculo, uc minúsculo, 6 dígitos puros e espaços nas pontas', () => {
    expect(normalizarUc('UC100123')).toBe('UC100123')
    expect(normalizarUc('uc100123')).toBe('UC100123')
    expect(normalizarUc('Uc100123')).toBe('UC100123')
    expect(normalizarUc('100123')).toBe('UC100123')
    expect(normalizarUc('  uc100123  ')).toBe('UC100123')
    expect(normalizarUc(' 000001 ')).toBe('UC000001')
  })

  it('rejeita 5 ou 7 dígitos, letras fora de UC e entradas vazias ou inválidas', () => {
    expect(normalizarUc('UC10012')).toBeNull()
    expect(normalizarUc('10012')).toBeNull()
    expect(normalizarUc('UC1001234')).toBeNull()
    expect(normalizarUc('1001234')).toBeNull()
    expect(normalizarUc('UC10012A')).toBeNull()
    expect(normalizarUc('AB100123')).toBeNull()
    expect(normalizarUc('UC 100123')).toBeNull()
    expect(normalizarUc('')).toBeNull()
    expect(normalizarUc('   ')).toBeNull()
  })
})
