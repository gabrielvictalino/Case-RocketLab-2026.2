import { useQuery } from '@tanstack/react-query'
import { api, desembrulhar, type ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'

export type Carga = components['schemas']['Carga']

export const QUERY_KEY_CARGA = ['meta', 'carga'] as const

export function useCarga() {
  return useQuery<Carga, ErroApi>({
    queryKey: QUERY_KEY_CARGA,
    queryFn: () => desembrulhar(api.GET('/api/v1/meta/carga')),
  })
}
