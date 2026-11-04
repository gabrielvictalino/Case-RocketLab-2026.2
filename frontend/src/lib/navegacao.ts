export function caminhoComPeriodo(caminho: string, p: { periodo?: string | null; comparacao?: string | null }): string {
  const params = new URLSearchParams()
  if (p.periodo) params.set('periodo', p.periodo)
  if (p.comparacao) params.set('comparacao', p.comparacao)
  const query = params.toString()
  return query ? `${caminho}?${query}` : caminho
}
