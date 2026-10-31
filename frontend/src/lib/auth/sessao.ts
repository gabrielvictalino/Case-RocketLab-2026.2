import { useSyncExternalStore } from 'react'
import type { components } from '@/lib/api/schema'

export type Token = components['schemas']['Token']

export type Cargo =
  | 'diretoria'
  | 'comercial'
  | 'atendimento'
  | 'perdas'
  | 'operacao'

export const ROTULO_CARGO: Record<Cargo, string> = {
  diretoria: 'Diretoria',
  comercial: 'Comercial',
  atendimento: 'Atendimento',
  perdas: 'Perdas',
  operacao: 'Operação',
}

export function cargoDaSessao(token: string | null | undefined): Cargo | null {
  if (!token || typeof token !== 'string') {
    return null
  }
  const partes = token.split('.')
  if (partes.length !== 3 || !partes[1]) {
    return null
  }
  try {
    const b64 = partes[1].replace(/-/g, '+').replace(/_/g, '/')
    const comPadding = b64.padEnd(b64.length + ((4 - (b64.length % 4)) % 4), '=')
    const binario = globalThis.atob(comPadding)
    const bytes = new Uint8Array(binario.length)
    for (let i = 0; i < binario.length; i++) {
      bytes[i] = binario.charCodeAt(i)
    }
    const json = new TextDecoder().decode(bytes)
    const payload: unknown = JSON.parse(json)
    if (payload === null || typeof payload !== 'object') {
      return null
    }
    const cargo = (payload as Record<string, unknown>).cargo
    if (typeof cargo === 'string' && Object.prototype.hasOwnProperty.call(ROTULO_CARGO, cargo)) {
      return cargo as Cargo
    }
    return null
  } catch {
    return null
  }
}

export interface Sessao {
  token: string
  login: string
  expiraEm: number
}

export const CHAVE_SESSAO = 'venergy.sessao'

const assinantes = new Set<() => void>()
let ultimoBruto: string | null = null
let ultimaSessao: Sessao | null = null

function notificarAssinantes(): void {
  for (const cb of assinantes) {
    cb()
  }
}

function removerDoStorage(): void {
  ultimoBruto = null
  ultimaSessao = null
  try {
    globalThis.localStorage?.removeItem(CHAVE_SESSAO)
  } catch {
    // Ignora falha de acesso ao storage (modo privado restrito / SSR)
  }
}

function sessaoValida(valor: unknown): valor is Sessao {
  if (valor === null || typeof valor !== 'object') {
    return false
  }
  const obj = valor as Record<string, unknown>
  return (
    typeof obj.token === 'string' &&
    obj.token.length > 0 &&
    typeof obj.login === 'string' &&
    obj.login.length > 0 &&
    typeof obj.expiraEm === 'number' &&
    Number.isFinite(obj.expiraEm)
  )
}

export function lerSessao(): Sessao | null {
  let bruto: string | null = null
  try {
    bruto = globalThis.localStorage?.getItem(CHAVE_SESSAO) ?? null
  } catch {
    return null
  }

  if (!bruto) {
    ultimoBruto = null
    ultimaSessao = null
    return null
  }

  if (bruto !== ultimoBruto || ultimaSessao === null) {
    try {
      const parsed: unknown = JSON.parse(bruto)
      if (!sessaoValida(parsed)) {
        removerDoStorage()
        return null
      }
      ultimoBruto = bruto
      ultimaSessao = {
        token: parsed.token,
        login: parsed.login,
        expiraEm: parsed.expiraEm,
      }
    } catch {
      removerDoStorage()
      return null
    }
  }

  if (Date.now() >= ultimaSessao.expiraEm) {
    removerDoStorage()
    return null
  }

  return ultimaSessao
}

export function salvarSessao(token: Token, login: string): Sessao {
  const novaSessao: Sessao = {
    token: token.access_token,
    login: login.trim(),
    expiraEm: Date.now() + token.expires_in * 1000,
  }
  const serializado = JSON.stringify(novaSessao)
  ultimoBruto = serializado
  ultimaSessao = novaSessao

  try {
    globalThis.localStorage?.setItem(CHAVE_SESSAO, serializado)
  } catch {
    // Ignora erro de escrita no storage
  }

  notificarAssinantes()
  return novaSessao
}

export function encerrarSessao(): void {
  const tinhaSessao = ultimaSessao !== null || ultimoBruto !== null
  removerDoStorage()
  if (tinhaSessao) {
    notificarAssinantes()
  } else {
    notificarAssinantes()
  }
}

/**
 * Encerra a sessão só se ela ainda for a que emitiu `token`. Um 401 atrasado
 * de uma requisição feita antes de outro login não pode apagar a sessão nova.
 */
export function encerrarSessaoDoToken(token: string | null): void {
  if (token !== null && lerSessao()?.token === token) {
    encerrarSessao()
  }
}

export function assinarSessao(cb: () => void): () => void {
  assinantes.add(cb)

  const aoMudarStorage = (evento: StorageEvent) => {
    if (evento.key === null || evento.key === CHAVE_SESSAO) {
      ultimoBruto = null
      ultimaSessao = null
      cb()
    }
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('storage', aoMudarStorage)
  }

  return () => {
    assinantes.delete(cb)
    if (typeof window !== 'undefined') {
      window.removeEventListener('storage', aoMudarStorage)
    }
  }
}

export function useSessao(): Sessao | null {
  return useSyncExternalStore(assinarSessao, lerSessao, () => null)
}
