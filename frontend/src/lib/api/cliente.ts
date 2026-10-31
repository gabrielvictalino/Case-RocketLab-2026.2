import createClient from 'openapi-fetch'
import type { paths } from '@/lib/api/schema'
import { encerrarSessaoDoToken, lerSessao } from '@/lib/auth/sessao'

const PREFIXO_BEARER = 'Bearer '

function tokenDaRequisicao(request: Request): string | null {
  const cabecalho = request.headers.get('Authorization')
  return cabecalho?.startsWith(PREFIXO_BEARER)
    ? cabecalho.slice(PREFIXO_BEARER.length)
    : null
}

const origemBase =
  typeof globalThis.location?.origin === 'string' &&
  globalThis.location.origin.startsWith('http')
    ? globalThis.location.origin
    : 'http://localhost'

export const api = createClient<paths>({
  baseUrl: origemBase,
  fetch: (request) => globalThis.fetch(request),
})

api.use({
  onRequest({ request }) {
    const sessao = lerSessao()
    if (sessao) {
      request.headers.set('Authorization', `Bearer ${sessao.token}`)
    }
    return request
  },
  onResponse({ request, response, schemaPath }) {
    if (response.status === 401 && schemaPath !== '/api/v1/auth/login') {
      encerrarSessaoDoToken(tokenDaRequisicao(request))
    }
    return response
  },
})

interface CorpoErroBackend {
  detail?: unknown
  code?: unknown
}

export class ErroApi extends Error {
  readonly status: number
  readonly code: string
  readonly detail: unknown

  constructor(status: number, corpo?: unknown) {
    const obj =
      corpo !== null && typeof corpo === 'object'
        ? (corpo as CorpoErroBackend)
        : undefined
    const detail = obj && 'detail' in obj ? obj.detail : corpo
    const code =
      obj && typeof obj.code === 'string' && obj.code.length > 0
        ? obj.code
        : 'ERRO'
    const mensagem =
      typeof detail === 'string' && detail.length > 0
        ? detail
        : `Erro na requisição (${status})`

    super(mensagem)
    this.name = 'ErroApi'
    this.status = status
    this.code = code
    this.detail = detail
  }
}

export async function desembrulhar<T>(
  promessa: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await promessa
  if (error !== undefined || !response.ok || data === undefined) {
    throw new ErroApi(response.status, error)
  }
  return data
}
