import { useSyncExternalStore } from 'react'
import type { components } from '@/lib/api/schema'

export type Token = components['schemas']['Token']

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
