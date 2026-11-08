import type { components } from '@/lib/api/schema'
import { cabecalhoCsv, decimalCsv, type LinhaCsv } from '@/lib/exportacao'

type Indicador = components['schemas']['Indicador']
type KPIs = components['schemas']['KPIs']
type PontoSerie = components['schemas']['PontoSerie']

export function linhasCsvVisaoGeral(dados: {
  kpis: KPIs
  serie: PontoSerie[]
  serieComparacao: PontoSerie[] | undefined
  periodo: string | null
  comparacao: string | null
  carga: string | undefined
}): LinhaCsv[] {
  const { kpis, serie, serieComparacao } = dados
  const indicadores: [string, Indicador][] = [
    ['Receita faturada (R$)', kpis.receita],
    ['Receita arrecadada (R$)', kpis.receita_arrecadada],
    ['Volume faturado (kWh)', kpis.volume_faturado_kwh],
    ['Tarifa média (R$/kWh)', kpis.tarifa_media],
    ['Inadimplência (%)', kpis.inadimplencia],
    ['UCs ativas', kpis.ucs.ativas],
    ['UCs com GD', kpis.ucs.com_gd],
    ['DEC (h)', kpis.continuidade.dec],
    ['FEC (vezes)', kpis.continuidade.fec],
    ['Taxa de acerto (%)', kpis.taxa_acerto],
  ]
  return [
    ...cabecalhoCsv({
      tela: 'Visão Geral',
      periodo: dados.periodo,
      comparacao: dados.comparacao,
      recortes: 'Todas as UCs',
      carga: dados.carga,
    }),
    [],
    ['Indicador', 'Período', 'Comparação', 'Variação', 'Variação (%)'],
    ...indicadores.map(([rotulo, indicador]) => [
      rotulo,
      decimalCsv(indicador.valor),
      decimalCsv(indicador.comparacao),
      decimalCsv(indicador.variacao),
      decimalCsv(indicador.variacao_pct),
    ]),
    [],
    [
      'Competência',
      'Receita (R$)',
      'Volume faturado (kWh)',
      'Competência comparada',
      'Receita comparada (R$)',
      'Volume comparado (kWh)',
    ],
    ...serie.map((ponto, indice) => {
      const comparado = serieComparacao?.[indice]
      return [
        ponto.competencia.slice(0, 7),
        decimalCsv(ponto.receita),
        decimalCsv(ponto.volume_faturado_kwh),
        comparado?.competencia.slice(0, 7),
        decimalCsv(comparado?.receita),
        decimalCsv(comparado?.volume_faturado_kwh),
      ]
    }),
  ]
}
