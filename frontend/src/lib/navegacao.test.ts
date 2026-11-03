import { expect, it } from 'vitest'
import { caminhoComPeriodo } from './navegacao'
it('preserva apenas período e comparação', () => {
  expect(caminhoComPeriodo('/receita', { periodo: '2025-01..2025-12', comparacao: '2024-01..2024-12' })).toBe('/receita?periodo=2025-01..2025-12&comparacao=2024-01..2024-12')
  expect(caminhoComPeriodo('/receita', {})).toBe('/receita')
})
