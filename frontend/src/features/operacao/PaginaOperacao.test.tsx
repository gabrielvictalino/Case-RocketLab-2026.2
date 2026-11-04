import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { PaginaOperacao } from './PaginaOperacao'

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

beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (requisicao: Request | string | URL) => {
    const url = typeof requisicao === 'string' ? requisicao : requisicao instanceof URL ? requisicao.href : requisicao.url
    const dados = url.includes('/api/v1/continuidade/serie')
      ? {
          periodo: '2026-01..2026-06',
          comparacao: '2025-01..2025-06',
          sem_evento_atipico: true,
          totais: {
            chi: 1250,
            interrupcoes: 18,
            numero_ucs: 500,
            dec: 9.84,
            fec: 5.12,
          },
          serie: [
            {
              competencia: '2026-01-01',
              chi: 200,
              interrupcoes: 3,
              numero_ucs: 500,
              dec: 1.5,
              fec: 0.8,
            },
          ],
          dados_comparacao: {
            totais: {
              chi: 1400,
              interrupcoes: 20,
              numero_ucs: 500,
              dec: 11.02,
              fec: 4.96,
            },
            serie: [
              {
                competencia: '2025-01-01',
                chi: 220,
                interrupcoes: 4,
                numero_ucs: 500,
                dec: 1.8,
                fec: 0.9,
              },
            ],
          },
        }
      : url.includes('/api/v1/continuidade/ranking')
        ? {
            periodo: '2026-01..2026-06',
            comparacao: '2025-01..2025-06',
            sem_evento_atipico: true,
            ordem: new URL(url).searchParams.get('ordem') ?? 'chi',
            ranking: [
              {
                alimentador: 'AL-01',
                municipio: 'Recife',
                chi: 1250,
                interrupcoes: 18,
                numero_ucs: 500,
                dec: 9.84,
                fec: 5.12,
                causas: [
                  { causa: 'Falha em equipamento', ocorrencias: 8, interrupcoes: 10 },
                ],
              },
            ],
            ranking_comparacao: null,
          }
        : url.includes('/api/v1/meta/filtros')
      ? {
          municipios: ['Recife', 'Olinda'],
          bairros: { Recife: ['Boa Viagem'], Olinda: ['Casa Caiada'] },
          classes: ['Residencial'],
          alimentadores: ['AL-01'],
        }
      : {
          id: '00000000-0000-0000-0000-000000000001',
          batch_id: 'gold_synthetic_v0_2_0',
          versao_contrato: '0.2.0-provisional',
          sintetica: true,
          carregado_em: '2026-07-01T00:00:00Z',
          competencia_inicial: '2022-07-01',
          competencia_mais_recente: '2026-06-01',
        }

    return new Response(JSON.stringify(dados), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function renderizarOperacao(caminho = '/operacao') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })

  const router = createMemoryRouter(
    [{ path: '/operacao', element: <PaginaOperacao /> }],
    { initialEntries: [caminho] },
  )

  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )

  return router
}

describe('Tela Operação', () => {
  it('mantem os indicadores e graficos em carregamento enquanto a carga global esta pendente', async () => {
    const fetchOriginal = vi.mocked(fetch).getMockImplementation()!

    vi.stubGlobal('fetch', vi.fn((requisicao: Request | string | URL) => {
      const url = typeof requisicao === 'string'
        ? requisicao
        : requisicao instanceof URL ? requisicao.href : requisicao.url

      if (url.includes('/api/v1/meta/carga')) {
        return new Promise<Response>(() => {})
      }

      return fetchOriginal(requisicao)
    }))

    renderizarOperacao()

    expect(screen.getByRole('article', { name: 'DEC' })).not.toHaveTextContent('Sem dados no período')
    expect(screen.getByRole('article', { name: 'FEC' })).not.toHaveTextContent('Sem dados no período')
    expect(screen.getByRole('status', { name: 'Carregando gráficos de continuidade' })).toBeInTheDocument()
    expect(screen.queryByText('Nenhum dado disponível')).not.toBeInTheDocument()
  })
  it('informa erro da carga global nos indicadores e no ranking', async () => {
    const fetchOriginal = vi.mocked(fetch).getMockImplementation()!

    vi.stubGlobal('fetch', vi.fn((requisicao: Request | string | URL) => {
      const url = typeof requisicao === 'string'
        ? requisicao
        : requisicao instanceof URL ? requisicao.href : requisicao.url

      if (url.includes('/api/v1/meta/carga')) {
        return Promise.resolve(new Response(
          JSON.stringify({ detail: 'Falha ao carregar período' }),
          { status: 500, headers: { 'Content-Type': 'application/json' } },
        ))
      }

      return fetchOriginal(requisicao)
    }))

    renderizarOperacao()

    await waitFor(() => {
      expect(screen.getByRole('article', { name: 'DEC' })).toHaveTextContent('Não foi possível carregar o período.')
      expect(screen.getByRole('article', { name: 'FEC' })).toHaveTextContent('Não foi possível carregar o período.')
    })

    expect(screen.getByText('Não foi possível carregar o período.', { selector: '.ve-empty-text' })).toBeInTheDocument()
  })
  it('inclui eventos atipicos por padrao e permite exclui-los nas duas consultas', async () => {
    renderizarOperacao()

    const urlsConsultadas = () => vi.mocked(fetch).mock.calls
      .map(([requisicao]) =>
        typeof requisicao === 'string'
          ? requisicao
          : requisicao instanceof URL
            ? requisicao.href
            : requisicao.url,
      )
      .filter((url) =>
        url.includes('/api/v1/continuidade/serie') ||
        url.includes('/api/v1/continuidade/ranking'),
      )

    await waitFor(() => {
      const urls = urlsConsultadas()
      expect(urls.some((url) => url.includes('/api/v1/continuidade/serie'))).toBe(true)
      expect(urls.some((url) => url.includes('/api/v1/continuidade/ranking'))).toBe(true)
      expect(urls.every((url) => new URL(url).searchParams.get('sem_evento_atipico') === 'false')).toBe(true)
    })

    fireEvent.click(screen.getByRole('checkbox', { name: /Com evento at.pico/ }))

    await waitFor(() => {
      const urls = urlsConsultadas().filter((url) =>
        new URL(url).searchParams.get('sem_evento_atipico') === 'true',
      )
      expect(urls.some((url) => url.includes('/api/v1/continuidade/serie'))).toBe(true)
      expect(urls.some((url) => url.includes('/api/v1/continuidade/ranking'))).toBe(true)
    })
  })
  it('permite ordenar as colunas do ranking pelos cabecalhos', async () => {
    renderizarOperacao()

    const cabecalhos = ['Alimentador', 'Município', 'CHI', 'DEC (h)', 'FEC (vezes)', 'Nº de UCs', 'Causa mais frequente']

    for (const nome of cabecalhos) {
      const botao = await screen.findByRole('button', { name: new RegExp(nome.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')) })
      expect(botao).toBeEnabled()
    }

    fireEvent.click(screen.getByRole('button', { name: /^CHI/ }))
    expect(screen.getByRole('columnheader', { name: /CHI/ })).toHaveAttribute('aria-sort', 'ascending')
  })
  it('limpa a ordenacao local ao mudar o seletor e ao limpar filtros', async () => {
    renderizarOperacao()

    const cabecalhoDec = await screen.findByRole('columnheader', { name: /DEC \(h\)/ })
    fireEvent.click(screen.getByRole('button', { name: /^DEC \(h\)/ }))
    expect(cabecalhoDec).toHaveAttribute('aria-sort', 'ascending')

    fireEvent.change(screen.getByLabelText('Ordenar por'), {
      target: { value: 'fec' },
    })

    await waitFor(() => {
      expect(screen.getByText(/Ordenado por FEC/)).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /DEC \(h\)/ })).not.toHaveAttribute('aria-sort')
    })

    fireEvent.click(screen.getByRole('button', { name: /^DEC \(h\)/ }))
    expect(screen.getByRole('columnheader', { name: /DEC \(h\)/ })).toHaveAttribute('aria-sort', 'ascending')

    fireEvent.click(screen.getByRole('button', { name: /Limpar filtros/ }))

    await waitFor(() => {
      expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
      expect(screen.getByRole('columnheader', { name: /DEC \(h\)/ })).not.toHaveAttribute('aria-sort')
    })
  })
  it('seleciona alimentador na serie sem filtrar o ranking', async () => {
    const router = renderizarOperacao('/operacao?periodo=2026-01..2026-06')

    const tabela = await screen.findByRole('table', { name: 'Ranking de alimentadores' })
    await waitFor(() => expect(tabela).toHaveTextContent('AL-01'))
    fireEvent.click(tabela.querySelector('tbody tr')!)

    await waitFor(() => {
      expect(new URLSearchParams(router.state.location.search).get('alimentador')).toBe('AL-01')
    })

    await waitFor(() => {
      const chamadas = vi.mocked(fetch).mock.calls.map(([requisicao]) =>
        typeof requisicao === 'string'
          ? requisicao
          : requisicao instanceof URL
            ? requisicao.href
            : requisicao.url,
      )
      expect(chamadas.some((url) =>
        url.includes('/api/v1/continuidade/serie') &&
        new URL(url).searchParams.get('alimentador') === 'AL-01',
      )).toBe(true)
      expect(chamadas.filter((url) =>
        url.includes('/api/v1/continuidade/ranking'),
      ).every((url) => !new URL(url).searchParams.has('alimentador'))).toBe(true)
    })

    expect(screen.getByRole('table', { name: 'Ranking de alimentadores' })).toHaveTextContent('AL-01')
  })

  it('exibe os indicadores, o aviso regulatório e o ranking', async () => {
    renderizarOperacao('/operacao?periodo=2026-01..2026-06&comparacao=2025-01..2025-06')

    expect(screen.getByRole('heading', { name: 'Operação' })).toBeInTheDocument()
    expect(screen.getByText(/limites regulatórios da ANEEL/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ranking de alimentadores' })).toBeInTheDocument()

    await waitFor(() => {
      expect(screen.getByText('Falha em equipamento')).toBeInTheDocument()
    })

    expect(screen.getByRole('article', { name: 'DEC' })).toHaveTextContent('9,84')
    expect(screen.getByRole('article', { name: 'FEC' })).toHaveTextContent('5,12')

    for (const coluna of [
      'Alimentador', 'Município', 'CHI', 'DEC (h)',
      'FEC (vezes)', 'Nº de UCs', 'Causa mais frequente',
    ]) {
      expect(screen.getByRole('columnheader', { name: coluna })).toBeInTheDocument()
    }
  })

  it('inclui eventos atípicos por padrão e inicia com ordenação CHI', () => {
    renderizarOperacao()

    expect(screen.getByRole('checkbox', { name: /Com evento atípico/ })).toBeChecked()
    expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
  })

  it('sincroniza eventos atípicos com a URL', async () => {
    const router = renderizarOperacao()

    fireEvent.click(screen.getByRole('checkbox', { name: /Com evento atípico/ }))

    await waitFor(() => {
      expect(new URLSearchParams(router.state.location.search).get('atipico')).toBe('0')
    })
  })

  it('sincroniza a ordenação com a URL e atualiza o subtítulo', async () => {
    const router = renderizarOperacao()

    fireEvent.change(screen.getByLabelText('Ordenar por'), {
      target: { value: 'fec' },
    })

    await waitFor(() => {
      expect(new URLSearchParams(router.state.location.search).get('ordem')).toBe('fec')
      expect(screen.getByText(/Ordenado por FEC/)).toBeInTheDocument()
    })
  })

  it('limpa filtros locais sem apagar o período global', async () => {
    const router = renderizarOperacao(
      '/operacao?periodo=2026-01..2026-06&comparacao=2025-01..2025-06&municipio=Recife&alimentador=AL-01&atipico=1&ordem=dec',
    )

    fireEvent.click(screen.getByRole('button', { name: /Limpar filtros/ }))

    await waitFor(() => {
      const parametros = new URLSearchParams(router.state.location.search)
      expect(parametros.get('periodo')).toBe('2026-01..2026-06')
      expect(parametros.get('comparacao')).toBe('2025-01..2025-06')
      for (const chave of ['municipio', 'bairro', 'alimentador', 'atipico', 'ordem']) {
        expect(parametros.has(chave)).toBe(false)
      }
      expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
      expect(screen.getByRole('checkbox', { name: /Com evento atípico/ })).toBeChecked()
    })
  })

  it('carrega os municípios e alimentadores disponíveis na API', async () => {
    renderizarOperacao()

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Recife' })).toBeInTheDocument()
      expect(screen.getByLabelText('Alimentador')).toBeEnabled()
    })

    expect(screen.getByRole('option', { name: 'Recife' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: 'AL-01' })).toBeInTheDocument()
  })

  it('preserva o período ao selecionar um município', async () => {
    const router = renderizarOperacao('/operacao?periodo=2026-01..2026-06')

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Recife' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Município'), {
      target: { value: 'Recife' },
    })

    await waitFor(() => {
      const parametros = new URLSearchParams(router.state.location.search)
      expect(parametros.get('municipio')).toBe('Recife')
      expect(parametros.get('periodo')).toBe('2026-01..2026-06')
    })
  })
})
