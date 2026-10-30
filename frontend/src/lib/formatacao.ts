export type ValorNumerico = number | string | null | undefined

const AUSENTE = '—'
const NBSP = '\u00a0'

const MESES = [
  'jan',
  'fev',
  'mar',
  'abr',
  'mai',
  'jun',
  'jul',
  'ago',
  'set',
  'out',
  'nov',
  'dez',
] as const

const REGEX_COMPETENCIA = /^(\d{4})-(\d{2})(?:-(\d{2}))?$/

const formatadorMoeda = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
})

const cacheDecimal = new Map<number, Intl.NumberFormat>([
  [
    0,
    new Intl.NumberFormat('pt-BR', {
      style: 'decimal',
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }),
  ],
  [
    2,
    new Intl.NumberFormat('pt-BR', {
      style: 'decimal',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  ],
])

const cachePercentual = new Map<number, Intl.NumberFormat>([
  [
    1,
    new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }),
  ],
  [
    2,
    new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }),
  ],
])

const cacheVariacao = new Map<number, Intl.NumberFormat>([
  [
    1,
    new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
      signDisplay: 'exceptZero',
    }),
  ],
  [
    2,
    new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
      signDisplay: 'exceptZero',
    }),
  ],
])

function obterFormatadorDecimal(casas: number): Intl.NumberFormat {
  let fmt = cacheDecimal.get(casas)
  if (!fmt) {
    fmt = new Intl.NumberFormat('pt-BR', {
      style: 'decimal',
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
    })
    cacheDecimal.set(casas, fmt)
  }
  return fmt
}

function obterFormatadorPercentual(casas: number): Intl.NumberFormat {
  let fmt = cachePercentual.get(casas)
  if (!fmt) {
    fmt = new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
    })
    cachePercentual.set(casas, fmt)
  }
  return fmt
}

function obterFormatadorVariacao(casas: number): Intl.NumberFormat {
  let fmt = cacheVariacao.get(casas)
  if (!fmt) {
    fmt = new Intl.NumberFormat('pt-BR', {
      style: 'percent',
      minimumFractionDigits: casas,
      maximumFractionDigits: casas,
      signDisplay: 'exceptZero',
    })
    cacheVariacao.set(casas, fmt)
  }
  return fmt
}

function converterNumero(valor: ValorNumerico): number | null {
  if (valor === null || valor === undefined) {
    return null
  }
  if (typeof valor === 'string') {
    const limpo = valor.trim()
    if (limpo === '') {
      return null
    }
    const numero = Number(limpo)
    return Number.isFinite(numero) ? numero : null
  }
  return Number.isFinite(valor) ? valor : null
}

export function formatarMoeda(valor: ValorNumerico): string {
  const numero = converterNumero(valor)
  if (numero === null) {
    return AUSENTE
  }
  return formatadorMoeda.format(numero)
}

export function formatarKwh(valor: ValorNumerico, casas = 0): string {
  const numero = converterNumero(valor)
  if (numero === null) {
    return AUSENTE
  }
  return `${obterFormatadorDecimal(casas).format(numero)}${NBSP}kWh`
}

export function formatarPercentual(fracao: ValorNumerico, casas = 1): string {
  const numero = converterNumero(fracao)
  if (numero === null) {
    return AUSENTE
  }
  return obterFormatadorPercentual(casas).format(numero)
}

export function formatarVariacao(fracao: ValorNumerico, casas = 1): string {
  const numero = converterNumero(fracao)
  if (numero === null) {
    return AUSENTE
  }
  return obterFormatadorVariacao(casas).format(numero)
}

export function formatarCompetencia(valor: string | null | undefined): string {
  if (valor === null || valor === undefined) {
    return AUSENTE
  }
  const match = REGEX_COMPETENCIA.exec(valor)
  if (!match) {
    throw new RangeError(`Competência inválida: "${valor}"`)
  }
  const ano = match[1]
  const mesNumero = Number(match[2])
  const diaTexto = match[3]

  if (mesNumero < 1 || mesNumero > 12) {
    throw new RangeError(`Mês inválido na competência: "${valor}"`)
  }
  if (diaTexto !== undefined) {
    const diaNumero = Number(diaTexto)
    if (diaNumero < 1 || diaNumero > 31) {
      throw new RangeError(`Dia inválido na competência: "${valor}"`)
    }
  }

  const nomeMes = MESES[mesNumero - 1]
  return `${nomeMes}/${ano}`
}
