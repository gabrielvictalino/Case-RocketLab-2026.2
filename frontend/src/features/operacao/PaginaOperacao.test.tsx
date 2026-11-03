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
    const dados = url.includes('/api/v1/meta/filtros')
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
  it('exibe os indicadores, o aviso regulatório e o ranking', () => {
    renderizarOperacao()

    expect(screen.getByRole('heading', { name: 'Operação' })).toBeInTheDocument()
    expect(screen.getByText(/limites regulatórios da ANEEL/)).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Ranking de alimentadores' })).toBeInTheDocument()
    expect(screen.getByText('Nenhum dado disponível')).toBeInTheDocument()

    for (const coluna of ['Alimentador', 'Município', 'CHI', 'DEC', 'FEC', 'UCs', 'Causa principal']) {
      expect(screen.getByRole('columnheader', { name: coluna })).toBeInTheDocument()
    }
  })

  it('inicia sem filtro atípico e com ordenação CHI', () => {
    renderizarOperacao()

    expect(screen.getByRole('checkbox', { name: /Com evento atípico/ })).not.toBeChecked()
    expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
  })

  it('sincroniza eventos atípicos com a URL', async () => {
    const router = renderizarOperacao()

    fireEvent.click(screen.getByRole('checkbox', { name: /Com evento atípico/ }))

    await waitFor(() => {
      expect(new URLSearchParams(router.state.location.search).get('atipico')).toBe('1')
    })
  })

  it('sincroniza a ordenação com a URL e atualiza o subtítulo', async () => {
    const router = renderizarOperacao()

    fireEvent.change(screen.getByLabelText('Ordenar por'), {
      target: { value: 'fec' },
    })

    await waitFor(() => {
      expect(new URLSearchParams(router.state.location.search).get('ordenar')).toBe('fec')
      expect(screen.getByText(/Ordenado por FEC/)).toBeInTheDocument()
    })
  })

  it('limpa filtros locais sem apagar o período global', async () => {
    const router = renderizarOperacao(
      '/operacao?periodo=2026-01:2026-06&comparacao=2025-01:2025-06&municipio=Recife&alimentador=AL-01&atipico=1&ordenar=dec',
    )

    fireEvent.click(screen.getByRole('button', { name: /Limpar filtros/ }))

    await waitFor(() => {
      const parametros = new URLSearchParams(router.state.location.search)
      expect(parametros.get('periodo')).toBe('2026-01:2026-06')
      expect(parametros.get('comparacao')).toBe('2025-01:2025-06')
      for (const chave of ['municipio', 'bairro', 'alimentador', 'atipico', 'ordenar']) {
        expect(parametros.has(chave)).toBe(false)
      }
      expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
      expect(screen.getByRole('checkbox', { name: /Com evento atípico/ })).not.toBeChecked()
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
    const router = renderizarOperacao('/operacao?periodo=2026-01:2026-06')

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'Recife' })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Município'), {
      target: { value: 'Recife' },
    })

    await waitFor(() => {
      const parametros = new URLSearchParams(router.state.location.search)
      expect(parametros.get('municipio')).toBe('Recife')
      expect(parametros.get('periodo')).toBe('2026-01:2026-06')
    })
  })
})