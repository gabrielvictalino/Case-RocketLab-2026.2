import { describe, expect, it } from 'vitest'
import type { components } from '@/lib/api/schema'
import { alinharSeries, montarCartoes } from './indicadores'

const ind = { valor: '1840000000', comparacao: '1000000000', variacao: '0.8', variacao_pct: '7.6' }
const kpis: components['schemas']['KPIs'] = {
  periodo: '2025-07..2026-06', comparacao: '2024-07..2025-06',
  carga: { id: '1', batch_id: '1', versao_contrato: '1', sintetica: true, carregado_em: '2026-01-01', competencia_inicial: '2022-07-01', competencia_mais_recente: '2026-06-01' },
  receita: ind, receita_arrecadada: ind, volume_faturado_kwh: ind, tarifa_media: ind,
  inadimplencia: ind, ucs: { ativas: ind, com_gd: ind }, continuidade: { dec: ind, fec: ind }, taxa_acerto: ind,
}
const ponto = (competencia: string, receita: string | null) => ({ competencia, receita, volume_faturado_kwh: receita })

describe('indicadores', () => {
  it('mapeia oito cartões, unidades, variações e destinos', () => {
    const c = montarCartoes(kpis, 'Anterior')
    expect(c).toHaveLength(8)
    expect(c[0]?.valor?.replaceAll('\u00a0', ' ')).toBe('R$ 1,84 bi')
    expect(c[0]?.variacao).toBeCloseTo(0.076)
    expect(c[4]?.variacao).toBe(0.8)
    expect(c.map(x => x.destino)).toEqual(['/receita', '/receita', '/receita', '/receita', '/receita', '/receita', '/operacao', '/perdas'])
    expect(c[3]?.sentidoFavoravel).toBe('neutro')
  })
  it('preserva dicas dos indicadores', () => {
    const cartoes = montarCartoes(kpis, 'Anterior')
    expect(cartoes.find(c => c.id === 'inadimplencia')?.dica).toBe(
      'Proporção da receita faturada ainda não arrecadada no período.',
    )
    expect(cartoes.find(c => c.id === 'continuidade')?.dica).toBe(
      'DEC e FEC acumulados para comparação entre períodos.',
    )
    expect(cartoes.find(c => c.id === 'taxa_acerto')?.dica).toBe(
      'Proporção de ordens de inspeção concluídas com irregularidade confirmada.',
    )
  })
  it('escolhe unidade de volume pela maior magnitude de ambas as séries', () => {
    const atual = [ponto('2026-01-01', '34222')]
    const resultado = alinharSeries(atual)
    expect(resultado.unidadeVolume).toBe('MWh')
    expect(resultado.volume[0]?.atual).toBe(34.222)
    expect(alinharSeries(atual, [ponto('2025-01-01', '1000000')]).unidadeVolume).toBe('GWh')
    expect(alinharSeries([ponto('2026-01-01', '999')]).unidadeVolume).toBe('kWh')
    const doisPontos = [ponto('2026-01-01', '34222'), ponto('2026-02-01', '34222')]
    const comparacao = [...doisPontos, ponto('2025-03-01', '5000000')]
    expect(alinharSeries(doisPontos, comparacao).unidadeVolume).toBe('MWh')
  })
  it('preserva zero e trata ausências individualmente', () => {
    const c = montarCartoes({ ...kpis, taxa_acerto: { ...ind, valor: null }, ucs: { ativas: { ...ind, comparacao: null }, com_gd: { ...ind, comparacao: '0', variacao_pct: null } } }, 'Anterior')
    expect(c[7]?.semDados).toBe(true)
    expect(c[5]?.pares?.[0]?.mensagemComparacao).toBe('Sem dados na comparação')
    expect(c[5]?.pares?.[0]?.variacao).toBeNull()
    expect(c[5]?.pares?.[1]?.valorComparado).toBe('0')
    expect(c[5]?.pares?.[1]?.variacao).toBeNull()
  })
  it('alinha por posição e conserva lacunas', () => {
    const atual = [ponto('2026-01-01', '10'), ponto('2026-02-01', null)]
    const maisCurta = alinharSeries(atual, [ponto('2025-01-01', '5')]).receita
    expect(maisCurta.map(x => x.comparacao)).toEqual([5, null])
    expect(maisCurta[1]?.atual).toBeNull()
    expect(alinharSeries(atual, undefined).receita.map(x => x.comparacao)).toEqual([null, null])
    expect(alinharSeries(atual, [ponto('2025-01-01', null), ponto('2025-02-01', '2'), ponto('2025-03-01', '3')]).receita.map(x => x.comparacao)).toEqual([null, 2])
  })
})
