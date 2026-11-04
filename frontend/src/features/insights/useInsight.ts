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
  versaoCarga: string | null,
): UseQueryResult<Insight, ErroApi> {
  return useQuery<Insight, ErroApi>({
    // A carga, o período, a comparação e os recortes estão na chave: mudar qualquer um
    // pede outro insight. A versão é o batch_id da carga, a mesma chave das outras
    // queries da tela.
    queryKey: ['insights', tela, versaoCarga, parametros],
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/insights/{tela}', {
          params: { path: { tela }, query: parametros as ParametrosInsight },
        }),
      ),
    enabled: parametros !== null && versaoCarga !== null,
    // O backend guarda o insight; repetir um 503 na hora só gastaria outra chamada ao modelo.
    retry: false,
  })
}
