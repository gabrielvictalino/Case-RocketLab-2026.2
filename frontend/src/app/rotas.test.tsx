import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { rotas } from '@/app/rotas'
import type { Carga } from '@/app/periodo/useCarga'
import { encerrarSessao, salvarSessao } from '@/lib/auth/sessao'

// Compatibiliza o AbortSignal do jsdom com o Request nativo (undici) do Node
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

const FILTROS_AMOSTRA = {
  municipios: ['Recife', 'Olinda'],
  bairros: { Recife: ['Boa Viagem'], Olinda: ['Casa Caiada'] },
  classes: ['Residencial', 'Comercial'],
  alimentadores: ['AL-01'],
}

const ORDENS_VAZIA = {
  items: [],
  total: 0,
  page: 1,
  size: 25,
}

beforeEach(() => {
  localStorage.clear()
  encerrarSessao()
  salvarSessao(
    { access_token: 'token-teste', token_type: 'bearer', expires_in: 3600 },
    'diretoria',
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request | string | URL) => {
      const url = typeof req === 'string' ? req : req instanceof URL ? req.href : req.url
      const corpo = url.includes('/api/v1/meta/filtros')
        ? FILTROS_AMOSTRA
        : url.includes('/api/v1/ordens-inspecao')
          ? ORDENS_VAZIA
          : CARGA_AMOSTRA
      return new Response(JSON.stringify(corpo), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderizarRota(caminhoInicial: string) {
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

describe('rotas do portal', () => {
  it('redireciona para /login preservando retorno quando não há sessão', async () => {
    encerrarSessao()
    const { router } = renderizarRota('/receita?municipio=Recife')

    expect(await screen.findByLabelText('Login')).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/login')
    expect(router.state.location.search).toBe(
      '?retorno=%2Freceita%3Fmunicipio%3DRecife',
    )
  })

  it('redireciona / para /visao-geral e exibe o h1 de Visão Geral', async () => {
    renderizarRota('/')
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Visão Geral' }),
    ).toBeInTheDocument()
  })

  it.each([
    ['/visao-geral', 'Visão Geral'],
    ['/receita', 'Receita'],
    ['/unidade-consumidora', 'Unidade Consumidora'],
    ['/perdas', 'Perdas'],
    ['/operacao', 'Operação'],
  ])('renderiza o h1 correto na rota %s', async (caminho, titulo) => {
    renderizarRota(caminho)
    expect(
      await screen.findByRole('heading', { level: 1, name: titulo }),
    ).toBeInTheDocument()
  })

  it('lista os 5 links na navegação lateral preservando periodo/comparacao e marca a rota ativa', async () => {
    renderizarRota('/receita')
    const nav = await screen.findByRole('navigation')
    const links = nav.querySelectorAll('a')
    expect(links).toHaveLength(5)

    const sufixoEsperado =
      '?periodo=2025-07..2026-06&comparacao=2024-07..2025-06'

    await waitFor(() => {
      expect(
        screen.getByRole('link', { name: 'Visão Geral' }),
      ).toHaveAttribute('href', `/visao-geral${sufixoEsperado}`)
    })

    expect(screen.getByRole('link', { name: 'Receita' })).toHaveAttribute(
      'href',
      `/receita${sufixoEsperado}`,
    )
    expect(
      screen.getByRole('link', { name: 'Unidade Consumidora' }),
    ).toHaveAttribute('href', `/unidade-consumidora${sufixoEsperado}`)
    expect(screen.getByRole('link', { name: 'Perdas' })).toHaveAttribute(
      'href',
      `/perdas${sufixoEsperado}`,
    )
    expect(screen.getByRole('link', { name: 'Operação' })).toHaveAttribute(
      'href',
      `/operacao${sufixoEsperado}`,
    )
    expect(screen.getByRole('link', { name: 'Receita' })).toHaveAttribute(
      'aria-current',
      'page',
    )
  })

  it('exibe a página 404 com botão do shadcn para rota inexistente', async () => {
    renderizarRota('/rota-que-nao-existe')
    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Página não encontrada',
      }),
    ).toBeInTheDocument()
    const linkVoltar = screen.getByRole('link', {
      name: 'Voltar para Visão Geral',
    })
    expect(linkVoltar).toHaveAttribute('data-slot', 'button')
    expect(linkVoltar).toHaveAttribute('href', '/visao-geral')
  })
})
