
import { describe, expect, it } from 'vitest'
import {
  filtrarEOrdenarAlimentadores,
  type AlimentadorOperacao,
} from './logicaOperacao'

const alimentadores: AlimentadorOperacao[] = [
  {
    id: 'a',
    nome: 'Alimentador A',
    municipio: 'Recife',
    chi: 100,
    dec: 3,
    fec: 2,
    quantidadeUcs: 1000,
    causaPrincipal: 'Vegetação',
  },
  {
    id: 'b',
    nome: 'Alimentador B',
    municipio: 'Olinda',
    chi: 300,
    dec: 1,
    fec: 4,
    quantidadeUcs: 800,
    causaPrincipal: 'Equipamento',
  },
  {
    id: 'c',
    nome: 'Alimentador C',
    municipio: 'Recife',
    chi: 200,
    dec: 5,
    fec: 1,
    quantidadeUcs: 1200,
    causaPrincipal: 'Clima',
  },
]

describe('Lógica da tela Operação', () => {
  it('ordena por CHI decrescente', () => {
    const resultado = filtrarEOrdenarAlimentadores(alimentadores, {
      ordenar: 'chi',
    })

    expect(resultado.map((item) => item.id)).toEqual(['b', 'c', 'a'])
  })

  it('ordena por DEC decrescente', () => {
    const resultado = filtrarEOrdenarAlimentadores(alimentadores, {
      ordenar: 'dec',
    })

    expect(resultado.map((item) => item.id)).toEqual(['c', 'a', 'b'])
  })

  it('ordena por FEC decrescente', () => {
    const resultado = filtrarEOrdenarAlimentadores(alimentadores, {
      ordenar: 'fec',
    })

    expect(resultado.map((item) => item.id)).toEqual(['b', 'a', 'c'])
  })

  it('filtra por município', () => {
    const resultado = filtrarEOrdenarAlimentadores(alimentadores, {
      municipio: 'Recife',
      ordenar: 'chi',
    })

    expect(resultado.map((item) => item.id)).toEqual(['c', 'a'])
  })

  it('filtra por alimentador', () => {
    const resultado = filtrarEOrdenarAlimentadores(alimentadores, {
      alimentador: 'a',
      ordenar: 'chi',
    })

    expect(resultado.map((item) => item.id)).toEqual(['a'])
  })

  it('não altera a lista original', () => {
    const original = alimentadores.map((item) => item.id)

    filtrarEOrdenarAlimentadores(alimentadores, {
      ordenar: 'chi',
    })

    expect(alimentadores.map((item) => item.id)).toEqual(original)
  })
})
