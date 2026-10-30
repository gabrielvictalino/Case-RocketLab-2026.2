import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { rotas } from '@/app/rotas'
import type { Carga } from '@/app/periodo/useCarga'
import { encerrarSessao, salvarSessao } from '@/lib/auth/sessao'

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
  salvarSessao(
    { access_token: 'token-barra', token_type: 'bearer', expires_in: 3600 },
    'diretoria',
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

describe('BarraPeriodo', () => {
  it('exibe metadados da carga e normaliza URL inválida preservando outros parâmetros', async () => {
    const { router } = renderizarApp(
      '/receita?periodo=invalido&municipio=Recife',
    )

    expect(await screen.findByText('Dados até jun/2026')).toBeInTheDocument()
    expect(
      screen.getByText('gold_synthetic_v0_2_0 (0.2.0-provisional)'),
    ).toBeInTheDocument()
    expect(screen.getByText('amostra sintética')).toBeInTheDocument()

    await waitFor(() => {
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get('periodo')).toBe('2025-07..2026-06')
      expect(params.get('comparacao')).toBe('2024-07..2025-06')
      expect(params.get('municipio')).toBe('Recife')
    })
  })

  it('normaliza URL com periodo válido e sem comparacao uma única vez para incluir a padrão', async () => {
    const { router } = renderizarApp('/visao-geral?periodo=2025-01..2025-12')

    await waitFor(() => {
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get('periodo')).toBe('2025-01..2025-12')
      expect(params.get('comparacao')).toBe('2024-01..2024-12')
    })
  })

  it('aplica atalho Primeiro ano × Últimos 12 meses, volta ao Padrão e ajusta extremos quando início > fim', async () => {
    const { router } = renderizarApp('/visao-geral')

    await screen.findByText('Dados até jun/2026')

    fireEvent.click(
      screen.getByRole('button', { name: 'Primeiro ano × Últimos 12 meses' }),
    )
    await waitFor(() => {
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get('periodo')).toBe('2025-07..2026-06')
      expect(params.get('comparacao')).toBe('2022-07..2023-06')
    })

    fireEvent.click(screen.getByRole('button', { name: 'Padrão' }))
    await waitFor(() => {
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get('periodo')).toBe('2025-07..2026-06')
      expect(params.get('comparacao')).toBe('2024-07..2025-06')
    })

    const selectFim = screen.getByLabelText('Fim do período')
    fireEvent.change(selectFim, { target: { value: '2025-03' } })

    await waitFor(() => {
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get('periodo')).toBe('2025-03..2025-03')
      expect(params.get('comparacao')).toBe('2024-03..2024-03')
    })
  })

  it('exibe "Nenhuma carga publicada" quando /meta/carga retorna 503 BASE_INDISPONIVEL sem quebrar a tela', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        new Response(
          JSON.stringify({
            detail: 'Nenhuma carga publicada; execute o importador',
            code: 'BASE_INDISPONIVEL',
          }),
          { status: 503, headers: { 'Content-Type': 'application/json' } },
        ),
      ),
    )

    renderizarApp('/visao-geral')

    expect(
      await screen.findByText('Nenhuma carga publicada'),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 1, name: 'Visão Geral' }),
    ).toBeInTheDocument()
  })
})
