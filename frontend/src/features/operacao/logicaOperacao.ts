
export type OrdenacaoOperacao = 'chi' | 'dec' | 'fec'

export type AlimentadorOperacao = {
  id: string
  nome: string
  municipio: string
  chi: number
  dec: number
  fec: number
  quantidadeUcs: number
  causaPrincipal: string
}

export type FiltrosOperacao = {
  municipio?: string
  alimentador?: string
  ordenar: OrdenacaoOperacao
}

export function filtrarEOrdenarAlimentadores(
  alimentadores: AlimentadorOperacao[],
  filtros: FiltrosOperacao,
): AlimentadorOperacao[] {
  return alimentadores
    .filter((item) => {
      if (filtros.municipio && item.municipio !== filtros.municipio) {
        return false
      }

      if (filtros.alimentador && item.id !== filtros.alimentador) {
        return false
      }

      return true
    })
    .sort((a, b) => {
      const diferenca = b[filtros.ordenar] - a[filtros.ordenar]

      return diferenca !== 0
        ? diferenca
        : a.nome.localeCompare(b.nome, 'pt-BR')
    })
}
