export type CelulaCsv = string | number | null | undefined
export type LinhaCsv = CelulaCsv[]

export const BOM = String.fromCharCode(0xfeff)
const SEPARADOR = ';'
const NUMERO_CSV = /^-?\d+(,\d+)?$/
const INICIO_DE_FORMULA = /^[=+\-@\t\r]/

function escrever(valor: CelulaCsv): string {
  if (valor === null || valor === undefined) return ''
  let texto = typeof valor === 'number' ? decimalCsv(valor) ?? '' : valor
  // Texto que o Excel executaria como fórmula entra com apóstrofo; número negativo não.
  if (INICIO_DE_FORMULA.test(texto) && !NUMERO_CSV.test(texto)) texto = `'${texto}`
  return /[;"\r\n]/.test(texto) ? `"${texto.replaceAll('"', '""')}"` : texto
}

/** CSV no padrão que o Excel em português abre sem assistente: `;`, vírgula decimal e BOM. */
export function montarCsv(linhas: LinhaCsv[]): string {
  const corpo = linhas.map((linha) => linha.map(escrever).join(SEPARADOR))
  return `${BOM}${corpo.join('\r\n')}\r\n`
}

export function decimalCsv(valor: string | number | null | undefined): string | null {
  return valor === null || valor === undefined ? null : String(valor).replace('.', ',')
}

export function fixoCsv(valor: number | null | undefined, casas = 2): string | null {
  return valor === null || valor === undefined ? null : decimalCsv(valor.toFixed(casas))
}

export function cabecalhoCsv(contexto: {
  tela: string
  periodo: string | null
  comparacao: string | null
  recortes: string
  carga: string | undefined
}): LinhaCsv[] {
  return [
    ['Tela', contexto.tela],
    ['Período', contexto.periodo],
    ['Comparação', contexto.comparacao ?? 'Sem comparação'],
    ['Recortes', contexto.recortes],
    ['Versão da carga', contexto.carga],
  ]
}

export function nomeCsv(tela: string, periodo: string): string {
  return `${tela}_${periodo.replace('..', '_a_')}.csv`
}

export function baixarArquivo(conteudo: Blob, nome: string): void {
  const url = URL.createObjectURL(conteudo)
  const link = document.createElement('a')
  link.href = url
  link.download = nome
  document.body.append(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function baixarCsv(nome: string, linhas: LinhaCsv[]): void {
  baixarArquivo(new Blob([montarCsv(linhas)], { type: 'text/csv;charset=utf-8' }), nome)
}
