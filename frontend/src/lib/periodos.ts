export interface Periodo {
  inicio: string
  fim: string
}

export interface Limites {
  inicial: string
  maisRecente: string
}

export interface PeriodosResolvidos {
  periodo: Periodo
  comparacao: Periodo | null
  normalizado: boolean
}

const REGEX_COMPETENCIA = /^(\d{4})-(0[1-9]|1[0-2])$/
const REGEX_PERIODO = /^(\d{4}-(0[1-9]|1[0-2]))\.\.(\d{4}-(0[1-9]|1[0-2]))$/

export function somarMeses(competencia: string, n: number): string {
  const match = REGEX_COMPETENCIA.exec(competencia)
  if (!match) {
    throw new RangeError(`Competência inválida: "${competencia}"`)
  }
  const ano = Number(match[1])
  const mes = Number(match[2])
  const totalMeses = ano * 12 + (mes - 1) + n
  const novoAno = Math.floor(totalMeses / 12)
  const restoMes = ((totalMeses % 12) + 12) % 12
  const novoMes = restoMes + 1

  return `${String(novoAno).padStart(4, '0')}-${String(novoMes).padStart(2, '0')}`
}

export function parsePeriodo(texto: string | null | undefined): Periodo | null {
  if (!texto) {
    return null
  }
  const match = REGEX_PERIODO.exec(texto)
  if (!match) {
    return null
  }
  const inicio = match[1]
  const fim = match[3]
  if (!inicio || !fim || inicio > fim) {
    return null
  }
  return { inicio, fim }
}

export function serializarPeriodo(periodo: Periodo): string {
  return `${periodo.inicio}..${periodo.fim}`
}

export function dentroDaBase(periodo: Periodo, limites: Limites): boolean {
  if (periodo.inicio > periodo.fim) {
    return false
  }
  return periodo.inicio >= limites.inicial && periodo.fim <= limites.maisRecente
}

export function comparacaoPadrao(
  periodo: Periodo,
  limites: Limites,
): Periodo | null {
  const anoInicio = Number(periodo.inicio.slice(0, 4))
  if (anoInicio <= 1) {
    return null
  }
  const candidato: Periodo = {
    inicio: somarMeses(periodo.inicio, -12),
    fim: somarMeses(periodo.fim, -12),
  }
  if (!dentroDaBase(candidato, limites)) {
    return null
  }
  return candidato
}

export function periodoPadrao(limites: Limites): {
  periodo: Periodo
  comparacao: Periodo | null
} {
  const inicioIdeal = somarMeses(limites.maisRecente, -11)
  const inicio =
    inicioIdeal < limites.inicial ? limites.inicial : inicioIdeal
  const periodo: Periodo = {
    inicio,
    fim: limites.maisRecente,
  }
  return {
    periodo,
    comparacao: comparacaoPadrao(periodo, limites),
  }
}

export function atalhoPrimeiroAno(limites: Limites): {
  periodo: Periodo
  comparacao: Periodo
} {
  const inicioUltimos12 = somarMeses(limites.maisRecente, -11)
  const periodo: Periodo = {
    inicio:
      inicioUltimos12 < limites.inicial ? limites.inicial : inicioUltimos12,
    fim: limites.maisRecente,
  }

  const fimPrimeiroAno = somarMeses(limites.inicial, 11)
  const comparacao: Periodo = {
    inicio: limites.inicial,
    fim:
      fimPrimeiroAno > limites.maisRecente
        ? limites.maisRecente
        : fimPrimeiroAno,
  }

  return { periodo, comparacao }
}

export function resolverPeriodos(
  params: URLSearchParams,
  limites: Limites,
): PeriodosResolvidos {
  const brutoPeriodo = params.get('periodo')
  const brutoComparacao = params.get('comparacao')

  const periodo = parsePeriodo(brutoPeriodo)
  if (!periodo || !dentroDaBase(periodo, limites)) {
    const padrao = periodoPadrao(limites)
    return {
      periodo: padrao.periodo,
      comparacao: padrao.comparacao,
      normalizado: true,
    }
  }

  const comparacao = parsePeriodo(brutoComparacao)
  if (!comparacao || !dentroDaBase(comparacao, limites)) {
    const padraoComparacao = comparacaoPadrao(periodo, limites)
    const esperadoNaUrl = padraoComparacao
      ? serializarPeriodo(padraoComparacao)
      : null
    return {
      periodo,
      comparacao: padraoComparacao,
      normalizado: brutoComparacao !== esperadoNaUrl,
    }
  }

  return {
    periodo,
    comparacao,
    normalizado: false,
  }
}

export function listarCompetencias(limites: Limites): string[] {
  if (limites.inicial > limites.maisRecente) {
    return []
  }
  const resultado: string[] = []
  let atual = limites.inicial
  while (atual <= limites.maisRecente) {
    resultado.push(atual)
    atual = somarMeses(atual, 1)
  }
  return resultado
}

export function ajustarInicioPeriodo(
  atual: Periodo,
  novoInicio: string,
): Periodo {
  return {
    inicio: novoInicio,
    fim: novoInicio > atual.fim ? novoInicio : atual.fim,
  }
}

export function ajustarFimPeriodo(atual: Periodo, novoFim: string): Periodo {
  return {
    inicio: novoFim < atual.inicio ? novoFim : atual.inicio,
    fim: novoFim,
  }
}
