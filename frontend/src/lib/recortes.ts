export const CHAVES_RECORTE = [
  'municipio',
  'bairro',
  'classe',
  'alimentador',
  'atipico',
] as const

export type ChaveRecorte = (typeof CHAVES_RECORTE)[number]

export interface RecortesUrl {
  municipio: string
  bairro: string
  classe: string
  alimentador: string
  atipico: boolean
}

export function lerRecortesUrl(params: URLSearchParams): RecortesUrl {
  const municipio = (params.get('municipio') ?? '').trim()
  const bairroBruto = (params.get('bairro') ?? '').trim()
  const bairro = municipio.length > 0 ? bairroBruto : ''
  const classe = (params.get('classe') ?? '').trim()
  const alimentador = (params.get('alimentador') ?? '').trim()
  const atipico = params.get('atipico') === '1'

  return {
    municipio,
    bairro,
    classe,
    alimentador,
    atipico,
  }
}

export function atualizarRecorteUrl(
  params: URLSearchParams,
  alteracoes: Partial<RecortesUrl>,
): URLSearchParams {
  const proximo = new URLSearchParams(params)
  const municipioAnterior = (params.get('municipio') ?? '').trim()

  if ('municipio' in alteracoes) {
    const novoMunicipio = (alteracoes.municipio ?? '').trim()
    if (novoMunicipio) {
      proximo.set('municipio', novoMunicipio)
    } else {
      proximo.delete('municipio')
    }
    if (novoMunicipio !== municipioAnterior) {
      proximo.delete('bairro')
    }
  }

  const municipioEfetivo = (proximo.get('municipio') ?? '').trim()

  if ('bairro' in alteracoes) {
    const novoBairro = (alteracoes.bairro ?? '').trim()
    if (municipioEfetivo && novoBairro) {
      proximo.set('bairro', novoBairro)
    } else {
      proximo.delete('bairro')
    }
  } else if (!municipioEfetivo) {
    proximo.delete('bairro')
  }

  if ('classe' in alteracoes) {
    const novaClasse = (alteracoes.classe ?? '').trim()
    if (novaClasse) {
      proximo.set('classe', novaClasse)
    } else {
      proximo.delete('classe')
    }
  }

  if ('alimentador' in alteracoes) {
    const novoAlimentador = (alteracoes.alimentador ?? '').trim()
    if (novoAlimentador) {
      proximo.set('alimentador', novoAlimentador)
    } else {
      proximo.delete('alimentador')
    }
  }

  if ('atipico' in alteracoes) {
    if (alteracoes.atipico) {
      proximo.set('atipico', '1')
    } else {
      proximo.delete('atipico')
    }
  }

  return proximo
}

export function limparRecortesUrl(
  params: URLSearchParams,
  chaves: ReadonlyArray<ChaveRecorte> = CHAVES_RECORTE,
): URLSearchParams {
  const proximo = new URLSearchParams(params)
  for (const chave of chaves) {
    proximo.delete(chave)
  }
  if (chaves.includes('municipio')) {
    proximo.delete('bairro')
  }
  return proximo
}

export function temRecorteAtivo(recortes: Partial<RecortesUrl>): boolean {
  return Boolean(
    (recortes.municipio && recortes.municipio.trim().length > 0) ||
      (recortes.bairro && recortes.bairro.trim().length > 0) ||
      (recortes.classe && recortes.classe.trim().length > 0) ||
      (recortes.alimentador && recortes.alimentador.trim().length > 0) ||
      recortes.atipico === true,
  )
}
