import type {
  CartaoKpiProps,
  ParKpi,
  SentidoFavoravel,
  TipoVariacao,
} from '@/components/CartaoKpi'
import type { PontoSerieComparativa } from '@/components/Graficos'
import {
  converterNumero,
  formatarCompetencia,
  formatarEnergiaCompacta,
  formatarMoeda,
  formatarMoedaCompacta,
  formatarNumero,
  formatarNumeroCompacto,
  formatarPercentual,
} from '@/lib/formatacao'
import type { components } from '@/lib/api/schema'

type Indicador = components['schemas']['Indicador']
type KPIs = components['schemas']['KPIs']
type PontoSerie = components['schemas']['PontoSerie']
type Formato = (valor: number) => string
export type CartaoVisaoGeral = CartaoKpiProps & { id: string; destino: string }
export const SEM_DADOS_PERIODO = 'Sem dados no período'

export const ROTULOS_INDICADORES = {
  receita: 'Receita faturada',
  receita_arrecadada: 'Receita arrecadada',
  volume: 'Volume faturado',
  tarifa: 'Tarifa média',
  inadimplencia: 'Inadimplência',
  ucs: 'UCs ativas e com GD',
  continuidade: 'Continuidade',
  taxa_acerto: 'Taxa de acerto',
} as const

function mapear(
  indicador: Indicador,
  formato: Formato,
  temComparacao: boolean,
  tipo: TipoVariacao = 'percentual',
) {
  const valor = converterNumero(indicador.valor)
  const comparacao = converterNumero(indicador.comparacao)
  const variacao = converterNumero(tipo === 'pp' ? indicador.variacao : indicador.variacao_pct)
  const temVariacao = valor !== null && comparacao !== null && variacao !== null && temComparacao
  return {
    valor: valor === null ? undefined : formato(valor),
    semDados: valor === null,
    valorComparado: comparacao === null ? undefined : formato(comparacao),
    mensagemComparacao: temComparacao && valor !== null && comparacao === null
      ? 'Sem dados na comparação'
      : undefined,
    variacao: temVariacao ? (tipo === 'pp' ? variacao : variacao / 100) : null,
    tipoVariacao: tipo,
  }
}

export function montarCartoes(kpis: KPIs, rotuloComparacao: string | null): CartaoVisaoGeral[] {
  const temComparacao = kpis.comparacao !== null
  const rodape = temComparacao ? (rotuloComparacao ?? kpis.comparacao ?? undefined) : undefined
  const item = (
    id: keyof typeof ROTULOS_INDICADORES,
    indicador: Indicador,
    formato: Formato,
    sentidoFavoravel: SentidoFavoravel,
    destino = '/receita',
    tipo: TipoVariacao = 'percentual',
  ): CartaoVisaoGeral => ({
    id,
    rotulo: ROTULOS_INDICADORES[id],
    destino,
    sentidoFavoravel,
    rotuloComparacao: rodape,
    semPeriodoComparacao: !temComparacao,
    ...mapear(indicador, formato, temComparacao, tipo),
  })
  const par = (
    subrotulo: string,
    indicador: Indicador,
    formato: Formato,
    sentidoFavoravel: SentidoFavoravel,
  ): ParKpi => ({
    subrotulo,
    sentidoFavoravel,
    ...mapear(indicador, formato, temComparacao),
  })
  return [
    item('receita', kpis.receita, formatarMoedaCompacta, 'alta'),
    item('receita_arrecadada', kpis.receita_arrecadada, formatarMoedaCompacta, 'alta'),
    item('volume', kpis.volume_faturado_kwh, formatarEnergiaCompacta, 'alta'),
    {
      ...item('tarifa', kpis.tarifa_media, v => formatarMoeda(v * 1000), 'neutro'),
      unidade: '/MWh',
    },
    {
      ...item('inadimplencia', kpis.inadimplencia, v => formatarPercentual(v / 100),
        'baixa', '/receita', 'pp'),
      dica: 'Proporção da receita faturada ainda não arrecadada no período.',
    },
    {
      id: 'ucs', rotulo: ROTULOS_INDICADORES.ucs, destino: '/receita',
      rotuloComparacao: rodape, semPeriodoComparacao: !temComparacao,
      pares: [
        par('Ativas', kpis.ucs.ativas, formatarNumeroCompacto, 'neutro'),
        par('Com GD', kpis.ucs.com_gd, formatarNumeroCompacto, 'neutro'),
      ],
    },
    {
      id: 'continuidade', rotulo: ROTULOS_INDICADORES.continuidade, destino: '/operacao',
      rotuloComparacao: rodape, semPeriodoComparacao: !temComparacao,
      dica: 'DEC e FEC acumulados para comparação entre períodos.',
      pares: [
        par('DEC (h)', kpis.continuidade.dec, v => formatarNumero(v, 2), 'baixa'),
        par('FEC (vezes)', kpis.continuidade.fec, v => formatarNumero(v, 2), 'baixa'),
      ],
    },
    {
      ...item('taxa_acerto', kpis.taxa_acerto, v => formatarPercentual(v / 100),
        'alta', '/perdas', 'pp'),
      dica: 'Proporção de ordens de inspeção concluídas com irregularidade confirmada.',
    },
  ]
}

export function alinharSeries(atual: PontoSerie[], comparacao?: PontoSerie[]): {
  receita: PontoSerieComparativa[]
  volume: PontoSerieComparativa[]
  unidadeVolume: 'kWh' | 'MWh' | 'GWh'
} {
  const maior = [...atual, ...(comparacao?.slice(0, atual.length) ?? [])].reduce((maximo, ponto) => {
    const valor = converterNumero(ponto.volume_faturado_kwh)
    return Math.max(maximo, Math.abs(valor ?? 0))
  }, 0)
  const divisor = maior >= 1e6 ? 1e6 : maior >= 1e3 ? 1e3 : 1
  const unidadeVolume = divisor === 1e6 ? 'GWh' : divisor === 1e3 ? 'MWh' : 'kWh'
  const montar = (campo: 'receita' | 'volume_faturado_kwh', escala: number) =>
    atual.map((p, i) => {
      const valor = converterNumero(p[campo])
      const anterior = converterNumero(comparacao?.[i]?.[campo])
      return {
        rotulo: formatarCompetencia(p.competencia),
        atual: valor === null ? null : valor / escala,
        comparacao: anterior === null ? null : anterior / escala,
      }
    })
  return {
    receita: montar('receita', 1),
    volume: montar('volume_faturado_kwh', divisor),
    unidadeVolume,
  }
}

export function temPontosExibiveis(pontos: ReadonlyArray<PontoSerieComparativa>): boolean {
  return pontos.some(ponto => ponto.atual !== null || ponto.comparacao != null)
}
