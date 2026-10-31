import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from '@testing-library/react'
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

const CARGA_FIXTURE: Carga = {
  id: '00000000-0000-0000-0000-000000000001',
  batch_id: 'gold_synthetic_v0_2_0',
  versao_contrato: '0.2.0-provisional',
  sintetica: true,
  carregado_em: '2026-07-01T00:00:00Z',
  competencia_inicial: '2022-07-01',
  competencia_mais_recente: '2026-06-01',
}

const FILTROS_FIXTURE = {
  municipios: ['Recife', 'Olinda'],
  bairros: {
    Recife: ['Boa Viagem', 'Pina'],
    Olinda: ['Casa Caiada'],
  },
  classes: ['Residencial', 'Comercial'],
  alimentadores: ['AL-RCF-07', 'AL-OLD-03'],
}

const ORDENS_FIXTURE = {
  items: [
    {
      id: 'ord-001',
      id_uc: 'UC100123',
      status: 'ABERTA',
      score: 0.85,
      motivos: ['Queda de consumo'],
      energia_recuperar_kwh: 4200,
      energia_recuperar_reais: 3150,
      inspetor: 'INSP-01',
      resultado: null,
      atualizado_em: '2026-06-15T14:30:00Z',
    },
    {
      id: 'ord-002',
      id_uc: 'UC100456',
      status: 'EM_CAMPO',
      score: 0.91,
      motivos: ['Medidor invertido'],
      energia_recuperar_kwh: 6100,
      energia_recuperar_reais: 4500,
      inspetor: 'INSP-02',
      resultado: null,
      atualizado_em: '2026-06-16T09:15:00Z',
    },
  ],
  total: 2,
  page: 1,
  size: 25,
}

beforeEach(() => {
  localStorage.clear()
  encerrarSessao()
  salvarSessao(
    { access_token: 'token-telas', token_type: 'bearer', expires_in: 3600 },
    'perdas',
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request | string | URL) => {
      const url =
        typeof req === 'string'
          ? req
          : req instanceof URL
            ? req.href
            : req.url
      if (url.includes('/api/v1/meta/filtros')) {
        return new Response(JSON.stringify(FILTROS_FIXTURE), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }
      if (url.includes('/api/v1/ordens-inspecao')) {
        const parsed = new URL(url, 'http://localhost')
        const st = parsed.searchParams.get('status')
        const filtrados = st
          ? ORDENS_FIXTURE.items.filter((i) => i.status === st)
          : ORDENS_FIXTURE.items
        return new Response(
          JSON.stringify({
            items: filtrados,
            total: filtrados.length,
            page: 1,
            size: 25,
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      return new Response(JSON.stringify(CARGA_FIXTURE), {
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

function renderizar(rotaInicial: string) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  const router = createMemoryRouter(rotas, {
    initialEntries: [rotaInicial],
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

describe('Telas do portal e PainelAgente', () => {
  it('renderiza Visão Geral com os 8 KPIs e painéis em estado indisponível e abre o PainelAgente', async () => {
    renderizar('/visao-geral')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Visão Geral' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Receita faturada')).toBeInTheDocument()
    expect(screen.getByText('Taxa de acerto')).toBeInTheDocument()
    expect(
      screen.getAllByText(
        'Dados ainda não disponíveis nesta versão do portal.',
      ).length,
    ).toBeGreaterThanOrEqual(8)

    fireEvent.click(
      screen.getByRole('button', { name: 'Perguntar ao agente' }),
    )
    expect(
      screen.getByRole('dialog', { name: 'Pergunte aos dados' }),
    ).toBeInTheDocument()
    expect(
      screen.getByText(
        'O agente ainda não está disponível nesta versão do portal.',
      ),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Pergunte sobre os dados')).toBeDisabled()
  })

  it('renderiza Receita populando selects de /meta/filtros e limpa recortes mantendo período', async () => {
    const { router } = renderizar('/receita')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Receita' }),
    ).toBeInTheDocument()

    const selectMunicipio = await screen.findByLabelText('Município')
    await waitFor(() => {
      expect(selectMunicipio.querySelectorAll('option').length).toBeGreaterThan(
        1,
      )
    })

    fireEvent.change(selectMunicipio, { target: { value: 'Recife' } })
    await waitFor(() => {
      expect(
        new URLSearchParams(router.state.location.search).get('municipio'),
      ).toBe('Recife')
    })

    fireEvent.click(screen.getByRole('button', { name: 'Limpar filtros' }))
    await waitFor(() => {
      const params = new URLSearchParams(router.state.location.search)
      expect(params.get('municipio')).toBeNull()
      expect(params.get('periodo')).toBe('2025-07..2026-06')
    })
  })

  it('valida e normaliza a busca por UC na tela Unidade Consumidora', async () => {
    const { router } = renderizar('/unidade-consumidora')

    expect(
      await screen.findByRole('heading', {
        level: 1,
        name: 'Unidade Consumidora',
      }),
    ).toBeInTheDocument()

    const inputUc = screen.getByLabelText('Número da UC')
    fireEvent.change(inputUc, { target: { value: '123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(
      /Informe uma UC válida/,
    )

    fireEvent.change(inputUc, { target: { value: '  100123 ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => {
      expect(
        new URLSearchParams(router.state.location.search).get('uc'),
      ).toBe('UC100123')
    })
  })

  it('lista ordens reais na aba Ordens de Perdas e filtra por status', async () => {
    const { router } = renderizar('/perdas')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Perdas' }),
    ).toBeInTheDocument()

    const abaOrdens = await screen.findByRole('tab', { name: /Ordens/ })
    await waitFor(() => {
      expect(abaOrdens).toHaveTextContent('2')
    })

    fireEvent.click(abaOrdens)

    expect(await screen.findByText('UC100123')).toBeInTheDocument()
    expect(screen.getByText('UC100456')).toBeInTheDocument()
    expect(screen.getByText('INSP-01')).toBeInTheDocument()
    expect(screen.getByText('15/06/2026 11:30')).toBeInTheDocument()

    const selectStatus = screen.getByLabelText('Status')
    fireEvent.change(selectStatus, { target: { value: 'EM_CAMPO' } })

    await waitFor(() => {
      expect(
        new URLSearchParams(router.state.location.search).get('status'),
      ).toBe('EM_CAMPO')
      expect(screen.queryByText('UC100123')).not.toBeInTheDocument()
      expect(screen.getByText('UC100456')).toBeInTheDocument()
    })
  })

  it('renderiza Operação com filtros de alimentador e toggle atípico', async () => {
    const { router } = renderizar('/operacao')

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Operação' }),
    ).toBeInTheDocument()

    const checkboxAtipico = screen.getByRole('checkbox')
    fireEvent.click(checkboxAtipico)

    await waitFor(() => {
      expect(
        new URLSearchParams(router.state.location.search).get('atipico'),
      ).toBe('1')
    })
  })
})
