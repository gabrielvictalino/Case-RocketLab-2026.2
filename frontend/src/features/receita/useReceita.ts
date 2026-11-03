import { useQuery } from '@tanstack/react-query'
import type { ParametrosPeriodoApi } from '@/app/periodo/usePeriodo'
import { api, desembrulhar } from '@/lib/api/cliente'

type Recorte = { municipio?: string; classe?: string }
const numerico = (v: unknown): boolean =>
  typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))
const percentual = (v: unknown): boolean => v === null || numerico(v)
function registro(v: unknown): Record<string, unknown> {
  return v !== null && typeof v === 'object' ? v as Record<string, unknown> : {}
}
function validarVariacao(v: unknown): boolean {
  const d = registro(v)
  const efeitos = registro(d.efeitos)
  return ['receita_base', 'receita_atual', 'variacao'].every((k) => numerico(d[k])) &&
    percentual(d.variacao_pct) && ['volume', 'reajuste', 'bandeira', 'mix'].every((k) => numerico(efeitos[k]))
}
function validar<T>(dados: T, valido: boolean): T {
  if (!valido) throw new Error('Resposta de receita inválida')
  return dados
}
export function useDecomposicao(p: ParametrosPeriodoApi | null, r: Recorte, batchId?: string) {
  return useQuery({
    queryKey: [
      'receita',
      'decomposicao',
      batchId,
      p?.periodo,
      p?.comparacao,
      r.municipio,
      r.classe,
    ],
    enabled: Boolean(p?.comparacao),
    queryFn: async () => {
      const d = await desembrulhar(
        api.GET('/api/v1/receita/decomposicao', { params: { query: { ...p!, ...r } } }),
      )
      return validar(d, validarVariacao(d))
    },
  })
}
export function useLocais(
  p: ParametrosPeriodoApi | null,
  r: Recorte,
  nivel: 'municipio' | 'bairro',
  batchId?: string,
) {
  return useQuery({
    queryKey: [
      'receita',
      'locais',
      batchId,
      p?.periodo,
      p?.comparacao,
      r.municipio,
      r.classe,
      nivel,
    ],
    enabled: Boolean(p?.comparacao),
    queryFn: async () => {
      const d = await desembrulhar(
        api.GET('/api/v1/receita/locais', {
          params: { query: { ...p!, ...r, nivel } },
        }),
      )
      return validar(d, Array.isArray(d.itens) && d.itens.every(validarVariacao) && validarVariacao(d.total))
    },
  })
}
export function useGrupos(p: ParametrosPeriodoApi | null, r: Recorte, batchId?: string) {
  return useQuery({
    queryKey: ['receita', 'grupos', batchId, p?.periodo, p?.comparacao, r.municipio, r.classe],
    enabled: Boolean(p?.comparacao),
    queryFn: async () => {
      const d = await desembrulhar(
        api.GET('/api/v1/receita/grupos', { params: { query: { ...p!, ...r } } }),
      )
      return validar(d, Array.isArray(d.itens) && d.itens.every((item) => numerico(item.volume_atual_kwh) && numerico(item.volume_base_kwh) && percentual(item.variacao_volume_pct)))
    },
  })
}
