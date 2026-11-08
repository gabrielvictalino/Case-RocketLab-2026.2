import type { components } from '@/lib/api/schema'
import { cabecalhoCsv, decimalCsv, fixoCsv, type LinhaCsv } from '@/lib/exportacao'
import { montarLinhasGrupos, montarLinhasLocais } from './receita'

type Decomposicao = components['schemas']['Decomposicao']
type Locais = components['schemas']['Locais']
type Grupos = components['schemas']['Grupos']

const porcentagem = (fracao: number | null) => (fracao === null ? null : fixoCsv(fracao * 100))

export function linhasCsvReceita(dados: {
  decomposicao: Decomposicao
  locais: Locais
  grupos: Grupos
  nivel: 'municipio' | 'bairro'
  periodo: string | null
  comparacao: string | null
  recortes: string
  carga: string | undefined
}): LinhaCsv[] {
  const { decomposicao, nivel } = dados
  return [
    ...cabecalhoCsv({
      tela: 'Receita',
      periodo: dados.periodo,
      comparacao: dados.comparacao,
      recortes: dados.recortes,
      carga: dados.carga,
    }),
    [],
    ['Cascata da receita', 'Valor (R$)'],
    ['Receita na comparação', decimalCsv(decomposicao.receita_base)],
    ['Efeito volume', decimalCsv(decomposicao.efeitos.volume)],
    ['Efeito reajuste', decimalCsv(decomposicao.efeitos.reajuste)],
    ['Efeito bandeira', decimalCsv(decomposicao.efeitos.bandeira)],
    ['Efeito mix', decimalCsv(decomposicao.efeitos.mix)],
    ['Receita no período', decimalCsv(decomposicao.receita_atual)],
    [],
    [
      nivel === 'municipio' ? 'Município' : 'Bairro',
      'Período (R$)',
      'Comparação (R$)',
      'Variação (%)',
      'Efeito-volume (R$)',
      'Da variação total (%)',
    ],
    ...montarLinhasLocais(dados.locais, nivel).map((linha) => [
      linha.rotulo,
      fixoCsv(linha.atual),
      fixoCsv(linha.base),
      porcentagem(linha.variacao),
      fixoCsv(linha.volume),
      porcentagem(linha.parte),
    ]),
    [],
    ['Grupo de UC', 'Volume no período (GWh)', 'Volume na comparação (GWh)', 'Variação (%)'],
    ...montarLinhasGrupos(dados.grupos).map((linha) => [
      linha.rotulo,
      fixoCsv(linha.atual, 6),
      fixoCsv(linha.base, 6),
      porcentagem(linha.variacao),
    ]),
  ]
}
