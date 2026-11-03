import { describe, expect, it } from 'vitest'
import {
  formatarCompetencia,
  formatarDataHoraPtBr,
  formatarDataPtBr,
  formatarKwh,
  formatarMoeda,
  formatarPercentual,
  formatarVariacao,
} from '@/lib/formatacao'

describe('formatacao pt-BR', () => {
  describe('formatarMoeda', () => {
    it('formata number positivo com NBSP após R$', () => {
      expect(formatarMoeda(1234.5)).toBe('R$\u00a01.234,50')
    })

    it('formata string Decimal vinda do Pydantic', () => {
      expect(formatarMoeda('1234.56')).toBe('R$\u00a01.234,56')
    })

    it('formata valor negativo', () => {
      expect(formatarMoeda(-1234.5)).toBe('-R$\u00a01.234,50')
    })

    it('retorna travessão para null, undefined, NaN ou string vazia/espaços', () => {
      expect(formatarMoeda(null)).toBe('—')
      expect(formatarMoeda(undefined)).toBe('—')
      expect(formatarMoeda(Number.NaN)).toBe('—')
      expect(formatarMoeda('')).toBe('—')
      expect(formatarMoeda('   ')).toBe('—')
    })
  })

  describe('formatarKwh', () => {
    it('formata com 0 casas por padrão e NBSP antes de kWh', () => {
      expect(formatarKwh(1234567)).toBe('1.234.567\u00a0kWh')
    })

    it('formata com 2 casas a partir de string', () => {
      expect(formatarKwh('1234.56', 2)).toBe('1.234,56\u00a0kWh')
    })

    it('retorna travessão para null ou string vazia/espaços', () => {
      expect(formatarKwh(null)).toBe('—')
      expect(formatarKwh('')).toBe('—')
      expect(formatarKwh('   ')).toBe('—')
    })
  })

  describe('formatarPercentual', () => {
    it('formata fração (0-1) com 1 casa por padrão', () => {
      expect(formatarPercentual(0.1234)).toBe('12,3%')
    })

    it('formata fração com 2 casas decimais', () => {
      expect(formatarPercentual('0.1234', 2)).toBe('12,34%')
    })

    it('retorna travessão para null ou string vazia/espaços', () => {
      expect(formatarPercentual(null)).toBe('—')
      expect(formatarPercentual('')).toBe('—')
      expect(formatarPercentual('   ')).toBe('—')
    })
  })

  describe('formatarVariacao', () => {
    it('inclui sinal explícito para variação positiva e negativa', () => {
      expect(formatarVariacao(0.052)).toBe('+5,2%')
      expect(formatarVariacao(-0.031)).toBe('-3,1%')
    })

    it('formata zero e valores arredondados para zero sem sinal', () => {
      expect(formatarVariacao(0)).toBe('0,0%')
      expect(formatarVariacao(-0.0001)).toBe('0,0%')
    })

    it('retorna travessão para null ou string vazia/espaços', () => {
      expect(formatarVariacao(null)).toBe('—')
      expect(formatarVariacao('')).toBe('—')
      expect(formatarVariacao('   ')).toBe('—')
    })
  })

  describe('formatarCompetencia', () => {
    it('formata AAAA-MM e AAAA-MM-DD sem deslocamento de fuso', () => {
      expect(formatarCompetencia('2025-07')).toBe('jul/2025')
      expect(formatarCompetencia('2025-07-01')).toBe('jul/2025')
      expect(formatarCompetencia('2026-01')).toBe('jan/2026')
    })

    it('retorna travessão para null ou undefined', () => {
      expect(formatarCompetencia(null)).toBe('—')
      expect(formatarCompetencia(undefined)).toBe('—')
    })

    it('lança RangeError para mês 13 ou formato inválido', () => {
      expect(() => formatarCompetencia('2025-13')).toThrow(RangeError)
      expect(() => formatarCompetencia('2025-00')).toThrow(RangeError)
      expect(() => formatarCompetencia('07/2025')).toThrow(RangeError)
      expect(() => formatarCompetencia('')).toThrow(RangeError)
    })
  })

  describe('formatarDataPtBr e formatarDataHoraPtBr (America/Recife)', () => {
    it('formata timestamps UTC no fuso America/Recife e preserva data pura AAAA-MM-DD', () => {
      expect(formatarDataHoraPtBr('2026-06-15T14:30:00Z')).toBe(
        '15/06/2026 11:30',
      )
      expect(formatarDataPtBr('2026-10-31T02:53:42Z')).toBe('30/10/2026')
      expect(formatarDataHoraPtBr('2026-10-31T03:53:42Z')).toBe(
        '31/10/2026 00:53',
      )
      expect(formatarDataPtBr('2026-07-01T00:00:00Z')).toBe('30/06/2026')
      expect(formatarDataPtBr('2026-07-01')).toBe('01/07/2026')
      expect(formatarDataPtBr(null)).toBe('—')
      expect(formatarDataHoraPtBr(null)).toBe('—')
    })
  })
})
