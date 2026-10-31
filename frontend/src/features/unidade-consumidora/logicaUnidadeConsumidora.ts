export function normalizarIdentificadorUC(valor: string): string | null {
  const identificador = valor.trim().toUpperCase()

  const numero = identificador.startsWith('UC')
    ? identificador.slice(2)
    : identificador

  if (!/^\d+$/.test(numero)) {
    return null
  }

  return `UC${numero}`
}
