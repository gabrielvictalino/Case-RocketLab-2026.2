import { describe, expect, it, vi } from 'vitest'
import {
  baixarArquivo,
  BOM,
  cabecalhoCsv,
  decimalCsv,
  fixoCsv,
  montarCsv,
  nomeCsv,
} from './exportacao'

describe('montarCsv', () => {
  it('usa ponto e vírgula, BOM e CRLF', () => {
    expect(montarCsv([['a', 1.5], [null, undefined]])).toBe(`${BOM}a;1,5\r\n;\r\n`)
  })

  it('começa com o BOM de verdade', () => {
    expect(montarCsv([['a']]).charCodeAt(0)).toBe(0xfeff)
  })

  it('protege separador, aspas e quebra de linha', () => {
    expect(montarCsv([['a;b', 'di"z', 'x\ny']])).toBe(`${BOM}"a;b";"di""z";"x\ny"\r\n`)
  })

  it.each(['=1+1', '+55', '@SOMA(A1)', '-1+2'])('neutraliza a fórmula %s', (texto) => {
    expect(montarCsv([[texto]])).toBe(`${BOM}'${texto}\r\n`)
  })

  it('mantém número negativo como número', () => {
    expect(montarCsv([['-12,50', -3.5]])).toBe(`${BOM}-12,50;-3,5\r\n`)
  })
})

describe('auxiliares', () => {
  it('converte decimais', () => {
    expect(decimalCsv('10.50')).toBe('10,50')
    expect(decimalCsv(null)).toBeNull()
    expect(fixoCsv(0.1 + 0.2)).toBe('0,30')
    expect(fixoCsv(null)).toBeNull()
  })

  it('monta o cabeçalho com todos os campos do contexto', () => {
    expect(
      cabecalhoCsv({ tela: 'Receita', periodo: 'jul/25', comparacao: null, recortes: 'todos', carga: 'b1' }),
    ).toEqual([
      ['Tela', 'Receita'],
      ['Período', 'jul/25'],
      ['Comparação', 'Sem comparação'],
      ['Recortes', 'todos'],
      ['Versão da carga', 'b1'],
    ])
  })

  it('só revoga a URL do arquivo depois do clique', () => {
    vi.useFakeTimers()
    URL.createObjectURL = vi.fn(() => 'blob:arquivo')
    URL.revokeObjectURL = vi.fn()
    baixarArquivo(new Blob(['x']), 'a.csv')
    expect(URL.revokeObjectURL).not.toHaveBeenCalled()
    vi.runAllTimers()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:arquivo')
    vi.useRealTimers()
  })

  it('tira os pontos do período no nome do arquivo', () => {
    expect(nomeCsv('receita', '2025-07..2026-06')).toBe('receita_2025-07_a_2026-06.csv')
  })
})
