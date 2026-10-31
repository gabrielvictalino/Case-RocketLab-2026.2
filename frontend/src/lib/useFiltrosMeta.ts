import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api, desembrulhar, type ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'

export type FiltrosMeta = components['schemas']['Filtros']

export const CHAVE_QUERY_FILTROS = ['meta', 'filtros'] as const

export function buscarFiltrosMeta(): Promise<FiltrosMeta> {
  return desembrulhar(api.GET('/api/v1/meta/filtros'))
}

export function useFiltrosMeta(): UseQueryResult<FiltrosMeta, ErroApi> {
  return useQuery<FiltrosMeta, ErroApi>({
    queryKey: CHAVE_QUERY_FILTROS,
    queryFn: buscarFiltrosMeta,
    staleTime: 60_000,
  })
}
