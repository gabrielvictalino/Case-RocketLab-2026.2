import { useQuery } from '@tanstack/react-query'
import { api, desembrulhar, type ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'

export type VisaoUC = components['schemas']['VisaoUC']

export function useUnidadeConsumidora(idUc: string | null) {
  return useQuery<VisaoUC, ErroApi>({
    queryKey: ['ucs', idUc],
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/ucs/{id_uc}', {
          params: { path: { id_uc: idUc! } },
        }),
      ),
    enabled: idUc !== null,

  })
}
