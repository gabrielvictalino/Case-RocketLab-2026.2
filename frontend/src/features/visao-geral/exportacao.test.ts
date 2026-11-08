import { expect, it } from 'vitest'
import type { components } from '@/lib/api/schema'
import { linhasCsvVisaoGeral } from './exportacao'

const indicador = (valor: string | null) => ({
  valor,
  comparacao: '90.5',
  variacao: '9.5',
  variacao_pct: '10.5',
})
const kpis = {
  receita: indicador('100.00'),
  receita_arrecadada: indicador('80'),
  volume_faturado_kwh: indicador('1000'),
  tarifa_media: indicador('0.75'),
  inadimplencia: indicador('2'),
  ucs: { ativas: indicador('10'), com_gd: indicador('3') },
  continuidade: { dec: indicador('1.5'), fec: indicador(null) },
  taxa_acerto: indicador('60'),
} as unknown as components['schemas']['KPIs']
const ponto = (competencia: string, receita: string | null) => ({
  competencia,
  receita,
  volume_faturado_kwh: '500.25',
})

it('leva indicadores, série, período, comparação, recorte e carga', () => {
  const linhas = linhasCsvVisaoGeral({
    kpis,
    serie: [ponto('2026-01-01', '10.50'), ponto('2026-02-01', null)],
    serieComparacao: [ponto('2025-01-01', '9.25')],
    periodo: 'jan/26 – fev/26',
    comparacao: 'jan/25 – fev/25',
    carga: 'lote-7',
  })
  expect(linhas.slice(0, 5)).toEqual([
    ['Tela', 'Visão Geral'],
    ['Período', 'jan/26 – fev/26'],
    ['Comparação', 'jan/25 – fev/25'],
    ['Recortes', 'Todas as UCs'],
    ['Versão da carga', 'lote-7'],
  ])
  expect(linhas).toContainEqual(['Receita faturada (R$)', '100,00', '90,5', '9,5', '10,5'])
  expect(linhas).toContainEqual(['FEC (vezes)', null, '90,5', '9,5', '10,5'])
  expect(linhas).toContainEqual(['2026-01', '10,50', '500,25', '2025-01', '9,25', '500,25'])
  expect(linhas).toContainEqual(['2026-02', null, '500,25', undefined, null, null])
})

it('funciona sem período de comparação', () => {
  const linhas = linhasCsvVisaoGeral({
    kpis,
    serie: [ponto('2026-01-01', '1')],
    serieComparacao: undefined,
    periodo: 'jan/26',
    comparacao: null,
    carga: 'lote-7',
  })
  expect(linhas).toContainEqual(['Comparação', 'Sem comparação'])
})
