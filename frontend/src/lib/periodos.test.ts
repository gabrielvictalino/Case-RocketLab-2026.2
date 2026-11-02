import { describe, expect, it } from 'vitest'
import {
  ajustarFimPeriodo,
  ajustarInicioPeriodo,
  atalhoPrimeiroAno,
  comparacaoPadrao,
  dentroDaBase,
  listarCompetencias,
  parsePeriodo,
  periodoPadrao,
  resolverPeriodos,
  serializarPeriodo,
  somarMeses,
  type Limites,
} from '@/lib/periodos'

const LIMITES_AMOSTRA: Limites = {
  inicial: '2022-07',
  maisRecente: '2026-06',
}

describe('somarMeses', () => {
  it('soma e subtrai meses atravessando virada de ano', () => {
    expect(somarMeses('2026-01', -1)).toBe('2025-12')
    expect(somarMeses('2025-12', 1)).toBe('2026-01')
    expect(somarMeses('2026-06', -11)).toBe('2025-07')
    expect(somarMeses('2022-07', 11)).toBe('2023-06')
    expect(somarMeses('2025-03', -15)).toBe('2023-12')
  })

  it('lança RangeError para competência malformada', () => {
    expect(() => somarMeses('2025-13', 1)).toThrow(RangeError)
    expect(() => somarMeses('abc', 1)).toThrow(RangeError)
  })
})

describe('parsePeriodo e serializarPeriodo', () => {
  it('faz parse e serialização ida e volta de período válido', () => {
    const original = '2025-07..2026-06'
    const parsed = parsePeriodo(original)
    expect(parsed).toEqual({ inicio: '2025-07', fim: '2026-06' })
    expect(serializarPeriodo(parsed!)).toBe(original)
  })

  it('aceita período de um único mês (inicio === fim)', () => {
    expect(parsePeriodo('2026-01..2026-01')).toEqual({
      inicio: '2026-01',
      fim: '2026-01',
    })
  })

  it('rejeita formatos inválidos, mês 13, início > fim e vazio', () => {
    expect(parsePeriodo('2025-13..2026-01')).toBeNull()
    expect(parsePeriodo('2025-00..2026-01')).toBeNull()
    expect(parsePeriodo('2026-06..2025-07')).toBeNull()
    expect(parsePeriodo('abc')).toBeNull()
    expect(parsePeriodo('')).toBeNull()
    expect(parsePeriodo(null)).toBeNull()
    expect(parsePeriodo(undefined)).toBeNull()
  })
})

describe('dentroDaBase, periodoPadrao e comparacaoPadrao', () => {
  it('calcula o padrão (últimos 12 meses × 12 meses anteriores) na amostra', () => {
    expect(periodoPadrao(LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-07', fim: '2026-06' },
      comparacao: { inicio: '2024-07', fim: '2025-06' },
    })
  })

  it('calcula padrão atravessando virada de ano', () => {
    const limites: Limites = { inicial: '2023-01', maisRecente: '2026-02' }
    expect(periodoPadrao(limites)).toEqual({
      periodo: { inicio: '2025-03', fim: '2026-02' },
      comparacao: { inicio: '2024-03', fim: '2025-02' },
    })
  })

  it('retorna comparacao null quando a base tem menos de 24 meses', () => {
    const limites18Meses: Limites = {
      inicial: '2025-01',
      maisRecente: '2026-06',
    }
    expect(periodoPadrao(limites18Meses)).toEqual({
      periodo: { inicio: '2025-07', fim: '2026-06' },
      comparacao: null,
    })
  })

  it('limita o início do período padrão quando a base tem menos de 12 meses', () => {
    const limites6Meses: Limites = {
      inicial: '2026-01',
      maisRecente: '2026-06',
    }
    expect(periodoPadrao(limites6Meses)).toEqual({
      periodo: { inicio: '2026-01', fim: '2026-06' },
      comparacao: null,
    })
  })

  it('valida se um período está dentro dos limites da base', () => {
    expect(
      dentroDaBase({ inicio: '2022-07', fim: '2026-06' }, LIMITES_AMOSTRA),
    ).toBe(true)
    expect(
      dentroDaBase({ inicio: '2022-06', fim: '2026-06' }, LIMITES_AMOSTRA),
    ).toBe(false)
    expect(
      dentroDaBase({ inicio: '2022-07', fim: '2026-07' }, LIMITES_AMOSTRA),
    ).toBe(false)
    expect(
      comparacaoPadrao({ inicio: '2022-07', fim: '2023-06' }, LIMITES_AMOSTRA),
    ).toBeNull()
  })
})

describe('atalhoPrimeiroAno', () => {
  it('retorna P1 (últimos 12 meses) × P0 (primeiro ano) na amostra', () => {
    expect(atalhoPrimeiroAno(LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-07', fim: '2026-06' },
      comparacao: { inicio: '2022-07', fim: '2023-06' },
    })
  })

  it('limita intervalos se a base tiver menos de 12 meses', () => {
    const limitesCurtos: Limites = {
      inicial: '2026-02',
      maisRecente: '2026-06',
    }
    expect(atalhoPrimeiroAno(limitesCurtos)).toEqual({
      periodo: { inicio: '2026-02', fim: '2026-06' },
      comparacao: { inicio: '2026-02', fim: '2026-06' },
    })
  })
})

describe('resolverPeriodos', () => {
  it('mantém período e comparação válidos da URL com normalizado=false', () => {
    const params = new URLSearchParams(
      'periodo=2025-01..2025-12&comparacao=2024-01..2024-12',
    )
    expect(resolverPeriodos(params, LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-01', fim: '2025-12' },
      comparacao: { inicio: '2024-01', fim: '2024-12' },
      normalizado: false,
    })
  })

  it.each([
    ['ausente', ''],
    ['mês inválido', 'periodo=2025-13..2026-01'],
    ['início > fim', 'periodo=2026-06..2025-07'],
    ['texto inválido', 'periodo=abc'],
    ['vazio', 'periodo='],
    ['fora da base (antes)', 'periodo=2021-01..2021-12'],
    ['fora da base (depois)', 'periodo=2025-07..2026-12'],
  ])('volta ao padrão completo quando periodo é %s', (_caso, query) => {
    const params = new URLSearchParams(query)
    expect(resolverPeriodos(params, LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-07', fim: '2026-06' },
      comparacao: { inicio: '2024-07', fim: '2025-06' },
      normalizado: true,
    })
  })

  it('normaliza comparação ausente ou inválida para a comparação padrão do período', () => {
    const semComparacao = new URLSearchParams('periodo=2025-01..2025-12')
    expect(resolverPeriodos(semComparacao, LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-01', fim: '2025-12' },
      comparacao: { inicio: '2024-01', fim: '2024-12' },
      normalizado: true,
    })

    const comparacaoInvalida = new URLSearchParams(
      'periodo=2025-01..2025-12&comparacao=2024-12..2024-01',
    )
    expect(resolverPeriodos(comparacaoInvalida, LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-01', fim: '2025-12' },
      comparacao: { inicio: '2024-01', fim: '2024-12' },
      normalizado: true,
    })

    const comparacaoForaDaBase = new URLSearchParams(
      'periodo=2025-01..2025-12&comparacao=2020-01..2020-12',
    )
    expect(resolverPeriodos(comparacaoForaDaBase, LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2025-01', fim: '2025-12' },
      comparacao: { inicio: '2024-01', fim: '2024-12' },
      normalizado: true,
    })
  })

  it('não marca normalizado=true quando comparacaoPadrao é null e comparacao já está ausente', () => {
    const noInicioDaBase = new URLSearchParams('periodo=2022-07..2023-06')
    expect(resolverPeriodos(noInicioDaBase, LIMITES_AMOSTRA)).toEqual({
      periodo: { inicio: '2022-07', fim: '2023-06' },
      comparacao: null,
      normalizado: false,
    })
  })
})

describe('listarCompetencias e ajustes de extremos', () => {
  it('lista todas as competências do intervalo inclusive', () => {
    expect(
      listarCompetencias({ inicial: '2025-11', maisRecente: '2026-02' }),
    ).toEqual(['2025-11', '2025-12', '2026-01', '2026-02'])
  })

  it('faz o outro extremo acompanhar quando início > fim', () => {
    expect(
      ajustarInicioPeriodo({ inicio: '2025-01', fim: '2025-06' }, '2025-09'),
    ).toEqual({ inicio: '2025-09', fim: '2025-09' })
    expect(
      ajustarFimPeriodo({ inicio: '2025-06', fim: '2025-12' }, '2025-03'),
    ).toEqual({ inicio: '2025-03', fim: '2025-03' })
  })
})
