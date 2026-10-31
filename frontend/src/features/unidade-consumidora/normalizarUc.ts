const PADRAO_UC = /^(?:UC)?(\d{6})$/i

export function normalizarUc(entrada: string): string | null {
  if (typeof entrada !== 'string') {
    return null
  }
  const limpo = entrada.trim()
  const correspondencia = PADRAO_UC.exec(limpo)
  if (!correspondencia) {
    return null
  }
  return `UC${correspondencia[1]}`
}
