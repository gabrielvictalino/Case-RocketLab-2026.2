import type { PontoSerieComparativa } from '@/components/Graficos'
import type { SerieContinuidade } from './useOperacao'

type Metrica = 'dec' | 'fec'

export function numeroContinuidade(
  valor: number | string | null | undefined,
): number | null {
  if (valor === null || valor === undefined || valor === '') return null
  const numero = Number(valor)
  return Number.isFinite(numero) ? numero : null
}

export function variacaoContinuidade(
  atual: number | string | null | undefined,
  anterior: number | string | null | undefined,
): number | null {
  const valorAtual = numeroContinuidade(atual)
  const valorAnterior = numeroContinuidade(anterior)

  if (valorAtual === null || valorAnterior === null || valorAnterior === 0) {
    return null
  }

  return ((valorAtual - valorAnterior) / Math.abs(valorAnterior)) * 100
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
    rotulo: ponto.competencia.slice(5, 7),
    atual: numeroContinuidade(ponto[metrica]),
    comparacao: comparacaoPorIndice.get(indice) ?? null,
  }))
}

export function formatarContinuidade(
  valor: number | string | null | undefined,
  casasDecimais = 2,
): string {
  const numero = numeroContinuidade(valor)
  if (numero === null) return '—'

  return numero.toLocaleString('pt-BR', {
    minimumFractionDigits: casasDecimais,
    maximumFractionDigits: casasDecimais,
  })
}
