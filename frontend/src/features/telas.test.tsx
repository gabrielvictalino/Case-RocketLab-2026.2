import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
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

const INDICADOR_FIXTURE = { valor: '1840000000', comparacao: '1000000000', variacao: '10', variacao_pct: '10' }
const KPIS_FIXTURE = { periodo: '2025-07..2026-06', comparacao: '2024-07..2025-06', carga: CARGA_FIXTURE, receita: INDICADOR_FIXTURE, receita_arrecadada: INDICADOR_FIXTURE, volume_faturado_kwh: INDICADOR_FIXTURE, tarifa_media: INDICADOR_FIXTURE, inadimplencia: INDICADOR_FIXTURE, ucs: { ativas: INDICADOR_FIXTURE, com_gd: INDICADOR_FIXTURE }, continuidade: { dec: INDICADOR_FIXTURE, fec: INDICADOR_FIXTURE }, taxa_acerto: { ...INDICADOR_FIXTURE, valor: null } }
type PontoSerieFixture = { competencia: string; receita: string | null; volume_faturado_kwh: string | null }
const PERIODO_ATUAL = '2025-07..2026-06'
const PERIODO_COMPARACAO = '2024-07..2025-06'
const pontoAtual = (receita: string | null, volume: string | null): PontoSerieFixture => ({
  competencia: '2025-07-01', receita, volume_faturado_kwh: volume,
})
const pontoComparacao = (receita: string | null, volume: string | null): PontoSerieFixture => ({
  competencia: '2024-07-01', receita, volume_faturado_kwh: volume,
})
let series: Record<string, PontoSerieFixture[]> = {}
let erroSerie: string | null = null
let comparacaoPendente: Promise<void> | null = null
let serieAtualRespondida = false
let endpointComErro = ''
beforeEach(() => {
  endpointComErro = ''
  erroSerie = null
  comparacaoPendente = null
  serieAtualRespondida = false
  series = {
    [PERIODO_ATUAL]: [pontoAtual('1000', '2000')],
    [PERIODO_COMPARACAO]: [pontoComparacao('900', '1800')],
  }
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
      const pathname = new URL(url, 'http://localhost').pathname
      if (pathname === endpointComErro) return new Response(JSON.stringify({ detail: 'erro' }), { status: 500 })
      if (pathname === '/api/v1/kpis') return new Response(JSON.stringify(KPIS_FIXTURE), { status: 200, headers: { 'Content-Type': 'application/json' } })
      if (pathname === '/api/v1/kpis/serie') {
        const periodo = new URL(url, 'http://localhost').searchParams.get('periodo') ?? ''
        if (periodo === PERIODO_COMPARACAO && comparacaoPendente) await comparacaoPendente
        if (periodo === erroSerie) return new Response('{}', { status: 500 })
        if (periodo === PERIODO_ATUAL) serieAtualRespondida = true
        return new Response(JSON.stringify({ serie: series[periodo] ?? [] }), {
          status: 200, headers: { 'Content-Type': 'application/json' },
        })
      }
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
  it('renderiza Visão Geral, navega com período resolvido e abre o PainelAgente', async () => {
    const { router } = renderizar('/visao-geral')
    const link = await screen.findByRole('link', { name: 'Receita faturada · ver detalhe' })
    expect(link).toHaveTextContent(/1,84\s*bi/)
    expect(screen.getByText('Sem dados no período')).toBeInTheDocument()
    expect(link.getAttribute('href')).toContain('periodo=2025-07..2026-06')
    expect(link.getAttribute('href')).toContain('comparacao=2024-07..2025-06')
    fireEvent.click(screen.getByRole('button', { name: 'Perguntar ao agente' }))
    expect(screen.getByRole('dialog', { name: 'Pergunte aos dados' })).toBeInTheDocument()
    expect(
      screen.getByRole('button', {
        name: 'Qual bairro mais perdeu volume residencial no último ano?',
      }),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Pergunte sobre os dados')).toBeEnabled()
    // Sem texto, não há o que enviar.
    expect(screen.getByRole('button', { name: 'Enviar pergunta' })).toBeDisabled()
    fireEvent.click(link)
    await waitFor(() => expect(router.state.location.pathname).toBe('/receita'))
    expect(router.state.location.search).toContain('periodo=2025-07..2026-06')
  })

  function painelSeries() {
    const painel = screen.getByRole('heading', { name: 'Receita e volume por competência' })
      .closest('section')
    if (!painel) throw new Error('Painel de séries não encontrado')
    return painel
  }

  it('exibe ambos os gráficos quando apenas a comparação tem dados', async () => {
    series[PERIODO_ATUAL] = [pontoAtual(null, null)]
    renderizar('/visao-geral')
    await waitFor(() => expect(painelSeries().querySelectorAll('.ve-chart')).toHaveLength(2))
    expect(within(painelSeries()).queryByText('Sem dados no período')).not.toBeInTheDocument()
  })

  it('mostra vazio no painel quando ambas as séries são nulas', async () => {
    series[PERIODO_ATUAL] = [pontoAtual(null, null)]
    series[PERIODO_COMPARACAO] = [pontoComparacao(null, null)]
    renderizar('/visao-geral')
    const painel = await screen.findByRole('heading', { name: 'Receita e volume por competência' })
    const secao = painel.closest('section')!
    expect(await within(secao).findByText('Sem dados no período')).toBeInTheDocument()
    expect(secao.querySelectorAll('.ve-chart')).toHaveLength(0)
  })

  it('aguarda comparação pendente antes de decidir estado vazio', async () => {
    series[PERIODO_ATUAL] = [pontoAtual(null, null)]
    let liberar!: () => void
    comparacaoPendente = new Promise<void>(resolve => { liberar = resolve })
    try {
      renderizar('/visao-geral')
      await waitFor(() => expect(vi.mocked(fetch).mock.calls.some(([req]) => {
        const url = new URL((req as Request).url)
        return url.pathname === '/api/v1/kpis/serie' &&
          url.searchParams.get('periodo') === PERIODO_COMPARACAO
      })).toBe(true))
      await screen.findByRole('link', { name: 'Receita faturada · ver detalhe' })
      await waitFor(() => expect(serieAtualRespondida).toBe(true))
      const painel = painelSeries()
      expect(within(painel).getByLabelText('Carregando dados')).toBeInTheDocument()
      expect(within(painel).queryByText('Sem dados no período')).not.toBeInTheDocument()
      await act(async () => { liberar() })
      await waitFor(() => expect(painel.querySelectorAll('.ve-chart')).toHaveLength(2))
    } finally {
      liberar()
    }
  })

  it('mostra vazio e nota quando só a comparação falha', async () => {
    series[PERIODO_ATUAL] = [pontoAtual(null, null)]
    erroSerie = PERIODO_COMPARACAO
    renderizar('/visao-geral')
    const painel = await screen.findByRole('heading', { name: 'Receita e volume por competência' })
    const secao = painel.closest('section')!
    expect(await within(secao).findByText('Sem dados no período')).toBeInTheDocument()
    expect(within(secao).getByText(/série de comparação indisponível/)).toBeInTheDocument()
  })

  it('mostra o gráfico de receita e vazio compacto identificado para volume', async () => {
    series[PERIODO_ATUAL] = [pontoAtual('1000', null)]
    series[PERIODO_COMPARACAO] = [pontoComparacao('900', null)]
    renderizar('/visao-geral')
    const painel = await screen.findByRole('heading', { name: 'Receita e volume por competência' })
    const secao = painel.closest('section')!
    expect(await within(secao).findByText('Volume faturado')).toBeInTheDocument()
    expect(within(secao).getByText('Sem dados no período')).toBeInTheDocument()
    expect(secao.querySelectorAll('.ve-chart')).toHaveLength(1)
  })

  it('mostra erro dos indicadores e mantém insight', async () => {
    endpointComErro = '/api/v1/kpis'
    renderizar('/visao-geral')
    expect(await screen.findByText('Não foi possível carregar os indicadores.')).toBeInTheDocument()
    // O bloco de insight segue na tela, com o próprio estado.
    expect(await screen.findByText(/^Insight indisponível/)).toBeInTheDocument()
  })

  it('mostra erro de carga sem esqueleto eterno', async () => {
    endpointComErro = '/api/v1/meta/carga'
    renderizar('/visao-geral')
    expect(await screen.findByText('Não foi possível carregar a carga publicada')).toBeInTheDocument()
    expect(screen.queryByLabelText('Carregando dados')).not.toBeInTheDocument()
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

  it('reinicia a paginação das ordens ao voltar/avançar no histórico', async () => {
    const todas = Array.from({ length: 60 }, (_, i) => ({
      ...ORDENS_FIXTURE.items[1]!,
      id: `ord-${i}`,
      id_uc: `UC9${String(i).padStart(5, '0')}`,
    }))
    const abertas = [ORDENS_FIXTURE.items[0]!]
    const fetchOrdens = vi.fn(async (req: Request) => {
      const url = new URL(req.url)
      if (!url.pathname.endsWith('/api/v1/ordens-inspecao')) {
        return new Response(
          JSON.stringify(
            url.pathname.endsWith('/meta/filtros')
              ? FILTROS_FIXTURE
              : CARGA_FIXTURE,
          ),
          { status: 200, headers: { 'Content-Type': 'application/json' } },
        )
      }
      const lista = url.searchParams.get('status') === 'ABERTA' ? abertas : todas
      const page = Number(url.searchParams.get('page') ?? '1')
      return new Response(
        JSON.stringify({
          items: lista.slice((page - 1) * 25, page * 25),
          total: lista.length,
          page,
          size: 25,
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      )
    })
    vi.stubGlobal('fetch', fetchOrdens)

    const { router } = renderizar('/perdas?aba=ordens')
    expect(await screen.findByText('Página 1 de 3')).toBeInTheDocument()

    // Filtra por status e volta no histórico para a lista sem filtro.
    fireEvent.change(screen.getByLabelText('Status'), {
      target: { value: 'ABERTA' },
    })
    expect(await screen.findByText('UC100123')).toBeInTheDocument()
    await act(() => router.navigate(-1))
    fireEvent.click(await screen.findByRole('button', { name: 'Próxima' }))
    expect(await screen.findByText('Página 2 de 3')).toBeInTheDocument()

    // Avançar restaura o status; a página 2 não pode sobreviver à troca.
    await act(() => router.navigate(1))
    expect(
      new URLSearchParams(router.state.location.search).get('status'),
    ).toBe('ABERTA')
    expect(await screen.findByText('UC100123')).toBeInTheDocument()
    const ultimaUrl = new URL(
      fetchOrdens.mock.calls
        .map(([req]) => req.url)
        .filter((u) => u.includes('/api/v1/ordens-inspecao'))
        .at(-1)!,
    )
    expect(ultimaUrl.searchParams.get('status')).toBe('ABERTA')
    expect(ultimaUrl.searchParams.get('page')).toBe('1')
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
