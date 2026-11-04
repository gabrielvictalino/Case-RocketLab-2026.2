import { describe, expect, it } from 'vitest'
import { montarSerieContinuidade, variacaoContinuidade } from './apresentacaoOperacao'

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
describe('montarSerieContinuidade', () => {
  it('inclui o ano nos rotulos de competencias de anos diferentes', () => {
    const dados = {
      serie: [
        { competencia: '2025-01', dec: 2, fec: 1 },
        { competencia: '2026-01', dec: 3, fec: 2 },
      ],
    } as unknown as Parameters<typeof montarSerieContinuidade>[0]

    const pontos = montarSerieContinuidade(dados, 'dec')

    expect(pontos.map((ponto) => ponto.rotulo)).toEqual([
      'jan/2025',
      'jan/2026',
    ])
    expect(pontos.map((ponto) => ponto.atual)).toEqual([2, 3])
  })
})
