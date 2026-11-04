import { useQuery } from '@tanstack/react-query'
import type { ParametrosPeriodoApi } from '@/app/periodo/usePeriodo'
import { api, desembrulhar } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'

export type SerieContinuidade =
  components['schemas']['app__modules__continuidade__schemas__Serie']

export type RankingContinuidade =
  components['schemas']['Ranking']

export type AlimentadorContinuidade =
  RankingContinuidade['ranking'][number]

export type OrdemContinuidade = 'chi' | 'dec' | 'fec'

export interface FiltrosOperacao {
  municipio?: string
  alimentador?: string
  comEventoAtipico: boolean
}

export function useSerieContinuidade(
  parametros: ParametrosPeriodoApi | null,
  filtros: FiltrosOperacao,
  batchId?: string,
) {
  return useQuery({
    queryKey: [
      'operacao',
      'serie',
      batchId,
      parametros?.periodo,
      parametros?.comparacao,
      filtros.municipio,
      filtros.alimentador,
      filtros.comEventoAtipico,
    ],
    enabled: Boolean(parametros),
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/continuidade/serie', {
          params: {
            query: {
              periodo: parametros!.periodo,
              comparacao: parametros!.comparacao,
              municipio: filtros.municipio || undefined,
              alimentador: filtros.alimentador || undefined,
              sem_evento_atipico: !filtros.comEventoAtipico,
            },
          },
        }),
      ),
  })
}

export function useRankingContinuidade(
  parametros: ParametrosPeriodoApi | null,
  filtros: FiltrosOperacao,
  ordem: OrdemContinuidade,
  batchId?: string,
) {
  return useQuery({
    queryKey: [
      'operacao',
      'ranking',
      batchId,
      parametros?.periodo,
      parametros?.comparacao,
      filtros.municipio,
      filtros.alimentador,
      filtros.comEventoAtipico,
      ordem,
    ],
    enabled: Boolean(parametros),
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/continuidade/ranking', {
          params: {
            query: {
              periodo: parametros!.periodo,
              comparacao: parametros!.comparacao,
              municipio: filtros.municipio || undefined,
              alimentador: filtros.alimentador || undefined,
              sem_evento_atipico: !filtros.comEventoAtipico,
              ordem,
            },
          },
        }),
      ),
  })
}
