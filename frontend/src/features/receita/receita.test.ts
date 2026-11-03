import { describe, expect, it } from 'vitest'
import { montarBarrasCascata } from '@/components/Graficos'
import { montarEixoCascata, formatadorCascata, formatarMoedaCompacta, formatarMoedaCompactaComSinal, montarLinhasGrupos, montarLinhasLocais, montarPassosCascata } from './receita'
import type { components } from '@/lib/api/schema'

describe('cálculos de apresentação da receita', () => {
  it('monta faixas descendentes, domínio truncado e fechamento', () => {
    const { barras, dominio } = montarBarrasCascata([
      { rotulo: 'início', valor: 100, tipo: 'inicio' },
      { rotulo: 'volume', valor: -10, tipo: 'delta' },
      { rotulo: 'fim', valor: 90, tipo: 'fim' },
    ])
    expect(barras[1]!.faixa).toEqual([100, 90])
    expect(barras[1]!.fim).toBeCloseTo(barras[2]!.valor, 2)
    expect(dominio).toEqual([89, 101])
    expect(barras[0]!.faixa).toEqual([89, 100])
  })
  it('fecha a cascata com os quatro efeitos da API', () => {
    const d = {
      receita_base: '100',
      receita_atual: '120',
      efeitos: { volume: '-10', reajuste: '20', bandeira: '5', mix: '5' },
    } as components['schemas']['Decomposicao']
    const passos = montarPassosCascata(d, { periodo: 'P1', comparacao: 'P0' })
    const { barras } = montarBarrasCascata(passos)
    expect(passos.map((p) => p.rotulo)).toEqual([
      'Receita',
      'Volume',
      'Reajuste',
      'Bandeira',
      'Mix',
      'Receita',
    ])
    expect([passos[0]!.detalhe, passos[5]!.detalhe]).toEqual(['P0', 'P1'])
    expect(barras[4]!.fim).toBeCloseTo(Number(d.receita_atual), 2)
    expect(barras[1]!.faixa).toEqual([100, 90])
  })
  it('mantém participação nula quando a variação total é zero', () => {
    const l = {
      total: { variacao: '0' },
      itens: [
        {
          municipio: 'Recife',
          bairro: null,
          receita_atual: '100',
          receita_base: '100',
          variacao: '0',
          variacao_pct: null,
          efeitos: { volume: '0' },
        },
      ],
    } as components['schemas']['Locais']
    expect(montarLinhasLocais(l, 'bairro')[0]).toMatchObject({
      rotulo: 'Bairro não informado',
      parte: null,
    })
  })
  it('ordena grupos e converte variação e volume', () => {
    const g = {
      itens: [
        {
          grupo_uc: 'DEMAIS',
          volume_atual_kwh: '1000000',
          volume_base_kwh: '2000000',
          variacao_volume_pct: '-10.50',
        },
        {
          grupo_uc: 'GD',
          volume_atual_kwh: '0',
          volume_base_kwh: '0',
          variacao_volume_pct: null,
        },
      ],
    } as components['schemas']['Grupos']
    expect(montarLinhasGrupos(g)).toMatchObject([
      { rotulo: 'Com GD' },
      { rotulo: 'Demais', atual: 1, variacao: -0.105 },
    ])
  })
})

it('formata valores compactos na escala do mockup e distingue valores próximos', () => {
  const normalizar = (texto: string) => texto.replaceAll('\u00a0', ' ')
  expect(normalizar(formatarMoedaCompacta(1712345678))).toBe('R$ 1,71 bi')
  expect(normalizar(formatarMoedaCompactaComSinal(12345678))).toBe('+R$ 12 mi')
  expect(normalizar(formatarMoedaCompactaComSinal(-9123456))).toBe('−R$ 9 mi')
  expect(normalizar(formatarMoedaCompactaComSinal(130000000))).toBe('+R$ 130 mi')
  const valores = [1710000000, 1710100000, 1710200000, 1710300000, 1710400000]
  const formatar = formatadorCascata(valores)
  expect(new Set(valores.map(formatar)).size).toBe(valores.length)
})

it('usa ticks redondos e formata totais independentemente do eixo', () => {
  const base = 1712345678
  const fim = 1722190000
  const { dominio } = montarBarrasCascata([
    { rotulo: 'base', tipo: 'inicio', valor: base },
    { rotulo: 'volume', tipo: 'delta', valor: fim - base },
    { rotulo: 'fim', tipo: 'fim', valor: fim },
  ])
  const eixo = montarEixoCascata(dominio)
  expect(eixo.ticks.length).toBeGreaterThanOrEqual(4)
  expect(eixo.ticks.length).toBeLessThanOrEqual(6)
  expect(eixo.ticks.every((tick) => tick >= dominio[0] && tick <= dominio[1])).toBe(true)
  expect(eixo.ticks.every((tick) => Number.isInteger(tick / eixo.passo))).toBe(true)
  const rotulos = eixo.ticks.map(eixo.formatar)
  expect(new Set(rotulos).size).toBe(rotulos.length)
  expect(rotulos.every((rotulo) => !/,\d{4,}/.test(rotulo))).toBe(true)
  const formatarTotais = formatadorCascata([base, fim])
  expect(formatarTotais(base)).not.toBe(formatarTotais(fim))
  expect([base, fim].map(formatarTotais).every((rotulo) => !/,\d{4,}/.test(rotulo))).toBe(true)
  const mockup = formatadorCascata([1710000000, 1840000000])
  expect(mockup(1710000000).replaceAll('\u00a0', ' ')).toBe('R$ 1,71 bi')
  expect(mockup(1840000000).replaceAll('\u00a0', ' ')).toBe('R$ 1,84 bi')
})
