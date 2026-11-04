import { describe, expect, it } from 'vitest'
import { variacaoContinuidade } from './apresentacaoOperacao'

describe('variacaoContinuidade', () => {
  it('retorna a variacao como fracao para o CartaoKpi', () => {
    expect(variacaoContinuidade(90, 100)).toBeCloseTo(-0.1)
    expect(variacaoContinuidade(110, 100)).toBeCloseTo(0.1)
  })

  it('aceita valores numericos recebidos como texto', () => {
    expect(variacaoContinuidade('9', '10')).toBeCloseTo(-0.1)
  })

  it('nao calcula variacao sem valores validos ou com base zero', () => {
    expect(variacaoContinuidade(null, 100)).toBeNull()
    expect(variacaoContinuidade(100, null)).toBeNull()
    expect(variacaoContinuidade(100, 0)).toBeNull()
    expect(variacaoContinuidade('invalido', 100)).toBeNull()
  })
})
