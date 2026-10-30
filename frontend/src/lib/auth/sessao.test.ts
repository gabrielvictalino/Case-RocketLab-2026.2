import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, desembrulhar, ErroApi } from '@/lib/api/cliente'
import {
  assinarSessao,
  CHAVE_SESSAO,
  encerrarSessao,
  lerSessao,
  salvarSessao,
} from '@/lib/auth/sessao'

describe('sessao e cliente da API', () => {
  beforeEach(() => {
    localStorage.clear()
    encerrarSessao()
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.useRealTimers()
  })

  it('salva, lê com referência estável e encerra a sessão', () => {
    const notificado = vi.fn()
    const cancelar = assinarSessao(notificado)

    const criada = salvarSessao(
      { access_token: 'jwt-123', token_type: 'bearer', expires_in: 3600 },
      'diretoria',
    )
    expect(notificado).toHaveBeenCalledTimes(1)
    expect(criada.token).toBe('jwt-123')
    expect(criada.login).toBe('diretoria')

    const lida1 = lerSessao()
    const lida2 = lerSessao()
    expect(lida1).not.toBeNull()
    expect(lida1).toBe(lida2)

    encerrarSessao()
    expect(lerSessao()).toBeNull()
    expect(localStorage.getItem(CHAVE_SESSAO)).toBeNull()

    cancelar()
  })

  it('limpa e devolve null quando a sessão está expirada', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-01T12:00:00Z'))

    salvarSessao(
      { access_token: 'jwt-exp', token_type: 'bearer', expires_in: 60 },
      'comercial',
    )
    expect(lerSessao()?.token).toBe('jwt-exp')

    vi.advanceTimersByTime(60_000)
    expect(lerSessao()).toBeNull()
    expect(localStorage.getItem(CHAVE_SESSAO)).toBeNull()
  })

  it('injeta Authorization Bearer nas requisições quando há sessão ativa', async () => {
    salvarSessao(
      { access_token: 'meu-token-secreto', token_type: 'bearer', expires_in: 3600 },
      'perdas',
    )

    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.headers.get('Authorization')).toBe('Bearer meu-token-secreto')
      return new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    })
    vi.stubGlobal('fetch', fetchMock)

    await api.GET('/api/v1/health')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('encerra a sessão ao receber 401 fora de /api/v1/auth/login', async () => {
    salvarSessao(
      { access_token: 'token-vencido', token_type: 'bearer', expires_in: 3600 },
      'operacao',
    )

    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({ detail: 'Token inválido', code: 'NAO_AUTORIZADO' }),
          { status: 401, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    await expect(
      desembrulhar(api.GET('/api/v1/meta/carga')),
    ).rejects.toBeInstanceOf(ErroApi)

    expect(lerSessao()).toBeNull()
  })

  it('não encerra sessão existente em caso de 401 no próprio /api/v1/auth/login', async () => {
    salvarSessao(
      { access_token: 'sessao-anterior', token_type: 'bearer', expires_in: 3600 },
      'diretoria',
    )

    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: 'Credenciais inválidas',
            code: 'CREDENCIAIS_INVALIDAS',
          }),
          { status: 401, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    await expect(
      desembrulhar(
        api.POST('/api/v1/auth/login', {
          body: { login: 'diretoria', senha: 'errada' },
        }),
      ),
    ).rejects.toMatchObject({
      status: 401,
      code: 'CREDENCIAIS_INVALIDAS',
    })

    expect(lerSessao()?.token).toBe('sessao-anterior')
  })
})
