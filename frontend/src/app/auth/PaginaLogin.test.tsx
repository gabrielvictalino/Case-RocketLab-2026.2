import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { rotas } from '@/app/rotas'
import type { Carga } from '@/app/periodo/useCarga'
import { encerrarSessao, lerSessao, salvarSessao } from '@/lib/auth/sessao'

const RequestNativo = globalThis.Request

class RequestCompativel extends RequestNativo {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      const copiaInit = { ...init }
      delete copiaInit.signal
      super(input, copiaInit)
      return
    }
    super(input, init)
  }
}

globalThis.Request = RequestCompativel
window.Request = RequestCompativel

const CARGA_AMOSTRA: Carga = {
  id: '00000000-0000-0000-0000-000000000001',
  batch_id: 'gold_synthetic_v0_2_0',
  versao_contrato: '0.2.0-provisional',
  sintetica: true,
  carregado_em: '2026-07-01T00:00:00Z',
  competencia_inicial: '2022-07-01',
  competencia_mais_recente: '2026-06-01',
}

beforeEach(() => {
  localStorage.clear()
  encerrarSessao()
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderizarApp(caminhoInicial: string) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  const router = createMemoryRouter(rotas, {
    initialEntries: [caminhoInicial],
  })
  return {
    router,
    ...render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>,
    ),
  }
}

describe('PaginaLogin e fluxo de autenticação', () => {
  it('autentica com sucesso e redireciona para o retorno válido', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (req: Request) => {
        if (req.url.endsWith('/api/v1/auth/login')) {
          return new Response(
            JSON.stringify({
              access_token: 'jwt-novo',
              token_type: 'bearer',
              expires_in: 28800,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          )
        }
        return new Response(JSON.stringify(CARGA_AMOSTRA), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )

    const { router } = renderizarApp(
      '/login?retorno=%2Freceita%3Fmunicipio%3DRecife',
    )

    fireEvent.change(screen.getByLabelText('Login'), {
      target: { value: 'comercial' },
    })
    fireEvent.change(screen.getByLabelText('Senha'), {
      target: { value: 'Demo-Venergy-2026!' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Receita' }),
    ).toBeInTheDocument()
    expect(lerSessao()?.login).toBe('comercial')
    expect(router.state.location.pathname).toBe('/receita')
    expect(
      new URLSearchParams(router.state.location.search).get('municipio'),
    ).toBe('Recife')
  })

  it('bloqueia open redirect quando retorno=//evil.com e envia para /visao-geral', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (req: Request) => {
        if (req.url.endsWith('/api/v1/auth/login')) {
          return new Response(
            JSON.stringify({
              access_token: 'jwt-seguro',
              token_type: 'bearer',
              expires_in: 28800,
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          )
        }
        return new Response(JSON.stringify(CARGA_AMOSTRA), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }),
    )

    const { router } = renderizarApp('/login?retorno=//evil.com')

    fireEvent.change(screen.getByLabelText('Login'), {
      target: { value: 'diretoria' },
    })
    fireEvent.change(screen.getByLabelText('Senha'), {
      target: { value: 'Demo-Venergy-2026!' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Visão Geral' }),
    ).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/visao-geral')
  })

  it('exibe mensagem de erro no formulário quando /auth/login retorna 401', async () => {
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

    renderizarApp('/login')

    fireEvent.change(screen.getByLabelText('Login'), {
      target: { value: 'diretoria' },
    })
    fireEvent.change(screen.getByLabelText('Senha'), {
      target: { value: 'errada' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Entrar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Login ou senha inválidos',
    )
    expect(lerSessao()).toBeNull()
  })

  it('leva de volta ao /login preservando retorno ao receber 401 fora do login ou clicar em Sair', async () => {
    salvarSessao(
      { access_token: 'jwt-ativo', token_type: 'bearer', expires_in: 3600 },
      'perdas',
    )
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(JSON.stringify(CARGA_AMOSTRA), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
      ),
    )

    const { router } = renderizarApp('/perdas')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Perdas' }),
    ).toBeInTheDocument()
    expect(screen.getByText('perdas')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Sair' }))

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/login')
    })
    expect(lerSessao()).toBeNull()
  })
})
