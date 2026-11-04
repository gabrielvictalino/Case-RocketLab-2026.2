import type { PontoSerieComparativa } from '@/components/Graficos'
import { converterNumero, formatarCompetencia, formatarNumero } from '@/lib/formatacao'
import type { SerieContinuidade } from './useOperacao'

type Metrica = 'dec' | 'fec'

export const numeroContinuidade = converterNumero

export function variacaoContinuidade(
  atual: number | string | null | undefined,
  anterior: number | string | null | undefined,
): number | null {
  const valorAtual = numeroContinuidade(atual)
  const valorAnterior = numeroContinuidade(anterior)

  if (valorAtual === null || valorAnterior === null || valorAnterior === 0) {
    return null
  }

  return (valorAtual - valorAnterior) / Math.abs(valorAnterior)
}

export function montarSerieContinuidade(
  dados: SerieContinuidade | undefined,
  metrica: Metrica,
): PontoSerieComparativa[] {
  if (!dados) return []

  const atual = dados.serie ?? []
  const anterior = dados.dados_comparacao?.serie ?? []

  const comparacaoPorIndice = new Map(
    anterior.map((ponto, indice) => [indice, numeroContinuidade(ponto[metrica])]),
  )

  return atual.map((ponto, indice) => ({
    rotulo: formatarCompetencia(ponto.competencia),
    atual: numeroContinuidade(ponto[metrica]),
    comparacao: comparacaoPorIndice.get(indice) ?? null,
  }))
}

export const formatarContinuidade = formatarNumero
