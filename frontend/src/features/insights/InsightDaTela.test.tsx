import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { rotas } from '@/app/rotas'
import type { Insight } from '@/features/insights/useInsight'
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

const CARGA = {
  id: '00000000-0000-0000-0000-000000000001',
  batch_id: 'gold_synthetic_v0_2_0',
  versao_contrato: '0.3.0-provisional',
  sintetica: true,
  carregado_em: '2026-07-01T00:00:00Z',
  competencia_inicial: '2022-07-01',
  competencia_mais_recente: '2026-06-01',
}

const FILTROS = {
  municipios: ['Recife', 'Olinda'],
  bairros: { Recife: ['Iputinga'], Olinda: ['Casa Caiada'] },
  classes: ['Residencial', 'Comercial'],
  alimentadores: ['ALM-REC-001'],
}

const INSIGHT: Insight = {
  periodo: '2025-07..2026-06',
  comparacao: '2024-07..2025-06',
  carga: CARGA,
  tela: 'visao-geral',
  modelo: 'gemini-3.1-flash-lite',
  gerado_em: '2026-11-03T12:00:00Z',
  observacoes: [
    {
      chave: 'receita',
      metrica: 'Receita faturada',
      texto: 'A receita faturada subiu 5,3% e chegou a R$ 170,3 milhões.',
      valores: [
        {
          trecho: '5,3%',
          chave: 'receita',
          metrica: 'Receita faturada',
          campo: 'variacao_pct',
          valor: '5.30',
          unidade: '%',
        },
        {
          trecho: '170,3 milhões',
          chave: 'receita',
          metrica: 'Receita faturada',
          campo: 'valor',
          valor: '170312456.78',
          unidade: 'R$',
        },
      ],
    },
    {
      chave: 'inadimplencia',
      metrica: 'Inadimplência',
      texto: 'A inadimplência foi de 7,42%, alta de 0,81 pp.',
      valores: [],
    },
  ],
}

type Roteiro = (url: URL) => Response | Promise<Response>

let roteiro: Roteiro
const pedidos: URL[] = []

function json(corpo: unknown, status = 200) {
  return new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  localStorage.clear()
  encerrarSessao()
  salvarSessao(
    { access_token: 'token-insight', token_type: 'bearer', expires_in: 3600 },
    'diretoria',
  )
  pedidos.length = 0
  roteiro = () => json(INSIGHT)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) => {
      const url = new URL(req.url)
      if (url.pathname.startsWith('/api/v1/insights/')) {
        pedidos.push(url)
        return roteiro(url)
      }
      if (url.pathname === '/api/v1/meta/filtros') {
        return json(FILTROS)
      }
      return json(CARGA)
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

function renderizarApp(caminhoInicial: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const router = createMemoryRouter(rotas, { initialEntries: [caminhoInicial] })
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

const PERIODOS = 'periodo=2025-07..2026-06&comparacao=2024-07..2025-06'

function pedido(n: number): URL {
  const url = pedidos[n]
  if (!url) {
    throw new Error(`O pedido ${n} de insight não foi feito`)
  }
  return url
}

async function blocoDoInsight() {
  return screen.findByRole('region', { name: 'Insight do período' })
}

describe('InsightDaTela', () => {
  it('mostra as observações numeradas, com a etiqueta, os números em destaque e o rodapé', async () => {
    renderizarApp(`/visao-geral?${PERIODOS}&municipio=Recife`)
    const bloco = await blocoDoInsight()
    const itens = await within(bloco).findAllByRole('listitem')
    expect(itens).toHaveLength(2)
    const [receita, inadimplencia] = itens as [HTMLElement, HTMLElement]
    expect(within(receita).getByText('1')).toBeInTheDocument()
    expect(within(receita).getByText('Receita faturada')).toBeInTheDocument()
    expect(within(receita).getByText('5,3%').tagName).toBe('STRONG')
    expect(within(receita).getByText('170,3 milhões').tagName).toBe('STRONG')
    expect(receita).toHaveTextContent('A receita faturada subiu 5,3% e chegou a R$ 170,3 milhões.')
    expect(within(inadimplencia).getByText('Inadimplência')).toBeInTheDocument()
    expect(
      within(bloco).getByText(
        'Gerado para jul/2025–jun/2026 × jul/2024–jun/2025 · carga gold_synthetic_v0_2_0',
      ),
    ).toBeInTheDocument()
    // A Visão Geral é de todas as UCs: os recortes da URL não vão para o insight.
    expect(pedidos).toHaveLength(1)
    expect(pedido(0).pathname).toBe('/api/v1/insights/visao-geral')
    expect(Object.fromEntries(pedido(0).searchParams)).toEqual({
      periodo: '2025-07..2026-06',
      comparacao: '2024-07..2025-06',
    })
  })

  it('mostra o esqueleto com "Gerando insight" enquanto espera', async () => {
    roteiro = () => new Promise<Response>(() => {})
    renderizarApp(`/visao-geral?${PERIODOS}`)
    const bloco = await blocoDoInsight()
    expect(await within(bloco).findByText('Gerando insight')).toBeInTheDocument()
    expect(within(bloco).getByRole('status', { name: 'Carregando dados' })).toBeInTheDocument()
  })

  it('fica indisponível num 503 sem derrubar o resto da tela', async () => {
    roteiro = () => json({ detail: 'sem observação válida', code: 'INSIGHT_INDISPONIVEL' }, 503)
    renderizarApp(`/visao-geral?${PERIODOS}`)
    const bloco = await blocoDoInsight()
    expect(
      await within(bloco).findByText('Insight indisponível para esta combinação de períodos'),
    ).toBeInTheDocument()
    expect(within(bloco).getByText('Os demais dados da tela seguem válidos.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Visão Geral' })).toBeInTheDocument()
    expect(screen.getByLabelText('Indicadores do período')).toBeInTheDocument()
    // Sem nova tentativa: o 503 não melhora na hora e cada tentativa iria ao modelo.
    expect(pedidos).toHaveLength(1)
  })

  it('explica o limite de insights por minuto', async () => {
    roteiro = () =>
      json({ detail: 'Limite atingido', code: 'LIMITE_DE_PERGUNTAS' }, 429)
    renderizarApp(`/visao-geral?${PERIODOS}`)
    const bloco = await blocoDoInsight()
    expect(await within(bloco).findByText(/Muitos insights gerados agora/)).toBeInTheDocument()
  })

  it('na Receita, envia os recortes da tela e recarrega quando o período muda', async () => {
    const router = renderizarApp(`/receita?${PERIODOS}&municipio=Recife&classe=Residencial`)
    const bloco = await blocoDoInsight()
    await within(bloco).findAllByRole('listitem')
    expect(pedido(0).pathname).toBe('/api/v1/insights/receita')
    expect(Object.fromEntries(pedido(0).searchParams)).toEqual({
      periodo: '2025-07..2026-06',
      comparacao: '2024-07..2025-06',
      municipio: 'Recife',
      classe: 'Residencial',
    })

    await act(() =>
      router.navigate(
        '/receita?periodo=2026-01..2026-06&comparacao=2025-01..2025-06&municipio=Recife',
      ),
    )
    await waitFor(() => expect(pedidos).toHaveLength(2))
    expect(Object.fromEntries(pedido(1).searchParams)).toEqual({
      periodo: '2026-01..2026-06',
      comparacao: '2025-01..2025-06',
      municipio: 'Recife',
    })
  })

  it('pede uma comparação quando a Receita não tem com o que comparar', async () => {
    roteiro = () =>
      json({ detail: 'Sem comparação', code: 'COMPARACAO_INDISPONIVEL' }, 422)
    renderizarApp(`/receita?${PERIODOS}`)
    const bloco = await blocoDoInsight()
    expect(
      await within(bloco).findByText(/Escolha um período de comparação para gerar o insight/),
    ).toBeInTheDocument()
  })
})
