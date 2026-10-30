import createClient from 'openapi-fetch'
import type { paths } from '@/lib/api/schema'

export const api = createClient<paths>({ baseUrl: '' })

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
