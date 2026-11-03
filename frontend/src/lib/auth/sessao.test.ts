import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api, desembrulhar, ErroApi } from '@/lib/api/cliente'
import {
  assinarSessao,
  cargoDaSessao,
  CHAVE_SESSAO,
  encerrarSessao,
  lerSessao,
  ROTULO_CARGO,
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

  it('avisa os assinantes quando a sessão vence, sem depender de leitura', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-01T12:00:00Z'))
    salvarSessao(
      { access_token: 'jwt-timer', token_type: 'bearer', expires_in: 60 },
      'comercial',
    )
    const notificado = vi.fn()
    const cancelar = assinarSessao(notificado)

    vi.advanceTimersByTime(59_999)
    await Promise.resolve()
    expect(notificado).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    await Promise.resolve()
    expect(notificado).toHaveBeenCalledTimes(1)
    expect(localStorage.getItem(CHAVE_SESSAO)).toBeNull()

    cancelar()
  })

  it('avisa os assinantes quando uma requisição encontra a sessão vencida', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-06-01T12:00:00Z'))
    salvarSessao(
      { access_token: 'jwt-vencido', token_type: 'bearer', expires_in: 60 },
      'operacao',
    )
    const notificado = vi.fn()
    const cancelar = assinarSessao(notificado)

    // Avança o relógio sem disparar o timer, como numa aba suspensa que acorda.
    vi.setSystemTime(new Date('2026-06-01T12:01:00Z'))
    const fetchMock = vi.fn(async (req: Request) => {
      expect(req.headers.get('Authorization')).toBeNull()
      return new Response(
        JSON.stringify({ detail: 'Não autenticado', code: 'NAO_AUTORIZADO' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      )
    })
    vi.stubGlobal('fetch', fetchMock)

    await expect(
      desembrulhar(api.GET('/api/v1/meta/carga')),
    ).rejects.toBeInstanceOf(ErroApi)

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(notificado).toHaveBeenCalledTimes(1)
    expect(lerSessao()).toBeNull()

    cancelar()
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

  it('ignora 401 atrasado de uma sessão anterior depois de um novo login', async () => {
    salvarSessao(
      { access_token: 'token-antigo', token_type: 'bearer', expires_in: 3600 },
      'comercial',
    )

    let responder: (r: Response) => void = () => {}
    vi.stubGlobal(
      'fetch',
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            responder = resolve
          }),
      ),
    )

    const pendente = desembrulhar(api.GET('/api/v1/meta/carga'))
    await vi.waitFor(() => expect(fetch).toHaveBeenCalledTimes(1))

    salvarSessao(
      { access_token: 'token-novo', token_type: 'bearer', expires_in: 3600 },
      'perdas',
    )

    responder(
      new Response(
        JSON.stringify({ detail: 'Token inválido', code: 'NAO_AUTORIZADO' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } },
      ),
    )
    await expect(pendente).rejects.toBeInstanceOf(ErroApi)

    expect(lerSessao()?.token).toBe('token-novo')
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

  it('decodifica cargoDaSessao para token válido, malformado e sem claim', () => {
    const codificarPayload = (obj: unknown) => {
      const b64 = btoa(JSON.stringify(obj))
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=+$/, '')
      return `eyJhbGciOiJIUzI1NiJ9.${b64}.assinatura`
    }

    expect(cargoDaSessao(codificarPayload({ sub: '1', cargo: 'perdas' }))).toBe(
      'perdas',
    )
    expect(
      cargoDaSessao(codificarPayload({ sub: '2', cargo: 'operacao' })),
    ).toBe('operacao')
    expect(ROTULO_CARGO.operacao).toBe('Operação')
    expect(ROTULO_CARGO.diretoria).toBe('Diretoria')

    // Sem claim cargo ou cargo desconhecido
    expect(cargoDaSessao(codificarPayload({ sub: '1' }))).toBeNull()
    expect(
      cargoDaSessao(codificarPayload({ sub: '1', cargo: 'admin' })),
    ).toBeNull()

    // Malformados / vazios
    expect(cargoDaSessao('token-sem-pontos')).toBeNull()
    expect(cargoDaSessao('a.%%%invalido%%%.c')).toBeNull()
    expect(cargoDaSessao('')).toBeNull()
    expect(cargoDaSessao(null)).toBeNull()
    expect(cargoDaSessao(undefined)).toBeNull()
  })
})
