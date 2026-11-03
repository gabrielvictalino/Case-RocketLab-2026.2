import { useQuery } from '@tanstack/react-query'
import type { ParametrosPeriodoApi } from '@/app/periodo/usePeriodo'
import { api, desembrulhar } from '@/lib/api/cliente'

export function useKpis(parametros: ParametrosPeriodoApi | null) {
  return useQuery({
    queryKey: ['kpis', parametros?.periodo ?? null, parametros?.comparacao ?? null],
    enabled: parametros !== null,
    queryFn: () => desembrulhar(api.GET('/api/v1/kpis', { params: { query: parametros! } })),
  })
}

export function useSerieKpis(periodo: string | null) {
  return useQuery({
    queryKey: ['kpis-serie', periodo],
    enabled: periodo !== null,
    queryFn: () => desembrulhar(api.GET('/api/v1/kpis/serie', { params: { query: { periodo: periodo! } } })),
  })
}
