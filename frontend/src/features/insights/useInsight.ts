import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import { api, desembrulhar, type ErroApi } from '@/lib/api/cliente'
import type { components, operations } from '@/lib/api/schema'

export type Insight = components['schemas']['Insight']
type Operacao = operations['insight_api_v1_insights__tela__get']['parameters']
export type TelaInsight = Operacao['path']['tela']
export type ParametrosInsight = Operacao['query']

export function useInsight(
  tela: TelaInsight,
  parametros: ParametrosInsight | null,
): UseQueryResult<Insight, ErroApi> {
  return useQuery<Insight, ErroApi>({
    // Período, comparação e recortes estão na chave: mudar qualquer um pede outro insight.
    queryKey: ['insights', tela, parametros],
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/insights/{tela}', {
          params: { path: { tela }, query: parametros as ParametrosInsight },
        }),
      ),
    enabled: parametros !== null,
    // O backend guarda o insight; repetir um 503 na hora só gastaria outra chamada ao modelo.
    retry: false,
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })
}
