import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { useCarga, type Carga } from '@/app/periodo/useCarga'
import { ErroApi } from '@/lib/api/cliente'
import {
  atalhoPrimeiroAno,
  comparacaoPadrao,
  periodoPadrao,
  resolverPeriodos,
  serializarPeriodo,
  type Limites,
  type Periodo,
} from '@/lib/periodos'

export interface ParametrosPeriodoApi {
  periodo: string
  comparacao?: string
}

export interface RetornoUsePeriodo {
  carga: Carga | undefined
  limites: Limites | null
  carregando: boolean
  erro: ErroApi | null
  periodo: Periodo | null
  comparacao: Periodo | null
  parametros: ParametrosPeriodoApi | null
  definirPeriodo: (p: Periodo) => void
  definirComparacao: (c: Periodo) => void
  aplicarPadrao: () => void
  aplicarPrimeiroAno: () => void
}

export function extrairLimitesCarga(
  carga: Pick<Carga, 'competencia_inicial' | 'competencia_mais_recente'>,
): Limites {
  return {
    inicial: carga.competencia_inicial.slice(0, 7),
    maisRecente: carga.competencia_mais_recente.slice(0, 7),
  }
}

export function usePeriodo(): RetornoUsePeriodo {
  const { data: carga, isPending, error } = useCarga()
  const [searchParams, setSearchParams] = useSearchParams()

  const limites = useMemo<Limites | null>(() => {
    if (!carga) {
      return null
    }
    return extrairLimitesCarga(carga)
  }, [carga])

  const erro = useMemo<ErroApi | null>(() => {
    if (!error) {
      return null
    }
    if (error instanceof ErroApi) {
      return error
    }
    return new ErroApi(0, String(error))
  }, [error])

  const resolvido = useMemo(() => {
    if (!limites) {
      return null
    }
    return resolverPeriodos(searchParams, limites)
  }, [limites, searchParams])

  const periodo = resolvido?.periodo ?? null
  const comparacao = resolvido?.comparacao ?? null

  const parametros = useMemo<ParametrosPeriodoApi | null>(() => {
    if (!periodo) {
      return null
    }
    const periodoStr = serializarPeriodo(periodo)
    if (comparacao) {
      return {
        periodo: periodoStr,
        comparacao: serializarPeriodo(comparacao),
      }
    }
    return { periodo: periodoStr }
  }, [periodo, comparacao])

  const atualizarUrl = useCallback(
    (novoPeriodo: Periodo, novaComparacao: Periodo | null) => {
      setSearchParams(
        (atual) => {
          const proximo = new URLSearchParams(atual)
          proximo.set('periodo', serializarPeriodo(novoPeriodo))
          if (novaComparacao) {
            proximo.set('comparacao', serializarPeriodo(novaComparacao))
          } else {
            proximo.delete('comparacao')
          }
          return proximo
        },
        { replace: true },
      )
    },
    [setSearchParams],
  )

  const definirPeriodo = useCallback(
    (novoPeriodo: Periodo) => {
      if (!limites) {
        return
      }
      const padraoComp = comparacaoPadrao(novoPeriodo, limites)
      atualizarUrl(novoPeriodo, padraoComp)
    },
    [limites, atualizarUrl],
  )

  const definirComparacao = useCallback(
    (novaComparacao: Periodo) => {
      if (!limites || !periodo) {
        return
      }
      atualizarUrl(periodo, novaComparacao)
    },
    [limites, periodo, atualizarUrl],
  )

  const aplicarPadrao = useCallback(() => {
    if (!limites) {
      return
    }
    const padrao = periodoPadrao(limites)
    atualizarUrl(padrao.periodo, padrao.comparacao)
  }, [limites, atualizarUrl])

  const aplicarPrimeiroAno = useCallback(() => {
    if (!limites) {
      return
    }
    const atalho = atalhoPrimeiroAno(limites)
    atualizarUrl(atalho.periodo, atalho.comparacao)
  }, [limites, atualizarUrl])

  return {
    carga,
    limites,
    carregando: isPending,
    erro,
    periodo,
    comparacao,
    parametros,
    definirPeriodo,
    definirComparacao,
    aplicarPadrao,
    aplicarPrimeiroAno,
  }
}
