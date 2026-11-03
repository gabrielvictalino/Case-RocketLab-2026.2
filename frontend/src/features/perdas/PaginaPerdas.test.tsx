import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { PaginaPerdas } from './PaginaPerdas'
import { salvarSessao, encerrarSessao } from '@/lib/auth/sessao'
const RequestNativo = globalThis.Request
class RequestCompativel extends RequestNativo {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      const copia = { ...init }
      delete copia.signal
      super(input, copia)
      return
    }
    super(input, init)
  }
}
globalThis.Request = RequestCompativel
window.Request = RequestCompativel
vi.mock('@/app/periodo/usePeriodo', () => ({
  usePeriodo: () => ({ periodo: null, carga: null }),
}))
const tokenComCargo = (cargo: string) =>
  `e30.${btoa(JSON.stringify({ cargo })).replace(/=/g, '')}.assinatura`
const itens = [
  {
    id_uc: 'UC100001',
    municipio: 'Recife',
    bairro: 'Pina',
    classe: 'Residencial',
    score: '0.90',
    motivos: ['Queda'],
    energia_recuperar_kwh: '10.20',
    energia_recuperar_reais: '5.00',
    inspecao_anterior: {
      id_inspecao: '1',
      data: '2025-01-10',
      inspetor: 'INSP-001',
      resultado: 'IRREGULARIDADE CONFIRMADA',
      tipo_irregularidade: 'fio',
      kwh_recuperado: '2.00',
      origem: 'gold',
    },
  },
  {
    id_uc: 'UC100002',
    municipio: 'Recife',
    bairro: 'Pina',
    classe: 'Residencial',
    score: '0.80',
    motivos: ['Leitura estimada'],
    energia_recuperar_kwh: '20.30',
    energia_recuperar_reais: '10.00',
    inspecao_anterior: null,
  },
]
const ordem = (status: string, id: string) => ({
  id,
  id_uc: 'UC100001',
  status,
  score: '0.90',
  motivos: ['Queda'],
  energia_recuperar_kwh: '10.20',
  energia_recuperar_reais: '5.00',
  inspetor: null,
  resultado: null,
  tipo_irregularidade: null,
  kwh_recuperado: null,
  motivo_cancelamento: null,
  criado_por: '1',
  atualizado_por: '1',
  criado_em: '2026-01-01T00:00:00Z',
  atualizado_em: '2026-01-01T00:00:00Z',
})
let fila = itens.slice()
let statusResposta = 201
let requests: { url: string; method: string; body: unknown }[] = []
beforeEach(() => {
  fila = itens.slice()
  statusResposta = 201
  requests = []
  salvarSessao(
    {
      access_token: tokenComCargo('perdas'),
      token_type: 'bearer',
      expires_in: 3600,
    },
    'perdas',
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) => {
      const url = new URL(req.url)
      let body: unknown
      if (req.method === 'POST') body = await req.clone().json()
      requests.push({ url: req.url, method: req.method, body })
      let resposta: unknown = {}
      let status = 200
      if (url.pathname.endsWith('/meta/filtros'))
        resposta = {
          municipios: ['Recife'],
          bairros: { Recife: ['Pina'] },
          classes: ['Residencial'],
          alimentadores: [],
        }
      else if (url.pathname.endsWith('/perdas/fila'))
        resposta = {
          items: fila,
          total: fila.length,
          page: 1,
          size: 25,
          totais: {
            pagina: {
              itens: fila.length,
              energia_recuperar_kwh: '30.50',
              energia_recuperar_reais: '15.00',
            },
            filtro: {
              itens: fila.length,
              energia_recuperar_kwh: '30.50',
              energia_recuperar_reais: '15.00',
            },
          },
        }
      else if (req.method === 'POST') {
        status = statusResposta
        if (status >= 400) resposta = { detail: 'erro' }
        else if (url.pathname.endsWith('/ordens-inspecao')) {
          fila = []
          resposta = {
            criadas: [ordem('ABERTA', '1')],
            rejeitadas: [
              { id_uc: 'UC100002', motivo: 'UC já possui ordem ativa' },
            ],
          }
        } else resposta = ordem('EM_CAMPO', '1')
      } else if (url.pathname.endsWith('/ordens-inspecao'))
        resposta = {
          items: [
            ordem('ABERTA', '1'),
            ordem('EM_CAMPO', '2'),
            ordem('CONCLUIDA', '3'),
            ordem('CANCELADA', '4'),
          ],
          total: 4,
          page: 1,
          size: 25,
        }
      return new Response(JSON.stringify(resposta), {
        status,
        headers: { 'Content-Type': 'application/json' },
      })
    }),
  )
})
afterEach(() => {
  cleanup()
  encerrarSessao()
  vi.unstubAllGlobals()
})
function abrir(url = '/perdas') {
  const router = createMemoryRouter(
    [{ path: '/perdas', element: <PaginaPerdas /> }],
    { initialEntries: [url] },
  )
  render(
    <QueryClientProvider
      client={
        new QueryClient({
          defaultOptions: {
            queries: { retry: false },
            mutations: { retry: false },
          },
        })
      }
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}
describe('Página Perdas', () => {
  it('exibe fila e filtro da URL, gera lote e mostra rejeitadas', async () => {
    abrir('/perdas?municipio=Recife')
    expect(
      await screen.findByText('Irregular · 10/01/2025'),
    ).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'UC100001' })).toHaveAttribute(
      'href',
      '/unidade-consumidora?uc=UC100001',
    )
    expect(
      requests.find((requisicao) => requisicao.url.includes('/perdas/fila'))
        ?.url,
    ).toContain('municipio=Recife')
    fireEvent.click(screen.getByLabelText('Selecionar UC100001'))
    fireEvent.click(screen.getByLabelText('Selecionar UC100002'))
    expect(screen.getByText(/30,50.*kWh a recuperar/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Gerar ordens (2)' }))
    expect(
      await screen.findByText(/UC100002 — UC já possui ordem ativa/),
    ).toBeInTheDocument()
    expect(
      requests.find((requisicao) => requisicao.method === 'POST')?.body,
    ).toEqual({
      ucs: ['UC100001', 'UC100002'],
    })
    await waitFor(() =>
      expect(
        requests.filter((requisicao) => requisicao.url.includes('/perdas/fila'))
          .length,
      ).toBeGreaterThan(1),
    )
  })
  it('exibe ações por status, despacha e devolve foco', async () => {
    abrir('/perdas?aba=ordens')
    const linhas = await screen.findAllByRole('row')
    expect(
      within(linhas[1]!).getByRole('button', { name: 'Despachar' }),
    ).toBeEnabled()
    expect(
      within(linhas[2]!).getByRole('button', { name: 'Registrar tentativa' }),
    ).toBeEnabled()
    expect(
      within(linhas[1]!).queryByRole('button', { name: 'Registrar tentativa' }),
    ).toBeNull()
    expect(
      within(linhas[1]!).queryByRole('button', { name: 'Registrar resultado' }),
    ).toBeNull()
    expect(within(linhas[3]!).queryByRole('button')).toBeNull()
    expect(within(linhas[4]!).queryByRole('button')).toBeNull()
    const botao = within(linhas[1]!).getByRole('button', { name: 'Despachar' })
    fireEvent.click(botao)
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Inspetor'), {
      target: { value: 'INSP-001' },
    })
    const consultasAntes = requests.filter(
      (requisicao) =>
        requisicao.url.includes('/ordens-inspecao') &&
        requisicao.method === 'GET',
    ).length
    fireEvent.click(within(dialog).getByRole('button', { name: 'Despachar' }))
    await waitFor(() =>
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument(),
    )
    await waitFor(() =>
      expect(
        requests.filter(
          (requisicao) =>
            requisicao.url.includes('/ordens-inspecao') &&
            requisicao.method === 'GET',
        ).length,
      ).toBeGreaterThan(consultasAntes),
    )
    expect(
      requests.find((requisicao) => requisicao.url.includes('/despachar'))
        ?.body,
    ).toEqual({
      inspetor: 'INSP-001',
    })
  })
  it('mostra erro 403 no lote e mantém seleção', async () => {
    statusResposta = 403
    abrir()
    fireEvent.click(await screen.findByLabelText('Selecionar UC100001'))
    fireEvent.click(screen.getByRole('button', { name: 'Gerar ordens (1)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Seu cargo')
    expect(screen.getByLabelText('Selecionar UC100001')).toBeChecked()
  })
  it('limpa o erro do lote ao mudar filtro', async () => {
    statusResposta = 403
    abrir()
    fireEvent.click(await screen.findByLabelText('Selecionar UC100001'))
    fireEvent.click(screen.getByRole('button', { name: 'Gerar ordens (1)' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Seu cargo')
    fireEvent.change(screen.getByLabelText('Município'), {
      target: { value: 'Recife' },
    })
    await waitFor(() =>
      expect(screen.queryByRole('alert')).not.toBeInTheDocument(),
    )
  })
  it('mostra erro 403 numa transição', async () => {
    statusResposta = 403
    abrir('/perdas?aba=ordens')
    fireEvent.click(await screen.findByRole('button', { name: 'Despachar' }))
    const dialogo = screen.getByRole('dialog')
    fireEvent.change(within(dialogo).getByLabelText('Inspetor'), {
      target: { value: 'INSP-001' },
    })
    fireEvent.click(within(dialogo).getByRole('button', { name: 'Despachar' }))
    expect(await within(dialogo).findByRole('alert')).toHaveTextContent(
      'Seu cargo',
    )
  })
  it('atualiza listas ao receber 409 numa transição', async () => {
    statusResposta = 409
    abrir('/perdas?aba=ordens')
    fireEvent.click(await screen.findByRole('button', { name: 'Despachar' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Inspetor'), {
      target: { value: 'INSP-001' },
    })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Despachar' }))
    expect(await within(dialog).findByRole('alert')).toHaveTextContent(
      'A lista será atualizada',
    )
    await waitFor(() =>
      expect(
        requests.filter(
          (requisicao) =>
            requisicao.url.includes('/ordens-inspecao') &&
            requisicao.method === 'GET',
        ).length,
      ).toBeGreaterThan(1),
    )
  })
  it('desabilita escrita para outro cargo', async () => {
    salvarSessao(
      {
        access_token: tokenComCargo('diretoria'),
        token_type: 'bearer',
        expires_in: 3600,
      },
      'diretoria',
    )
    abrir()
    expect(await screen.findByLabelText('Selecionar UC100001')).toBeDisabled()
    fireEvent.click(screen.getByRole('tab', { name: /Ordens/ }))
    expect(
      await screen.findByRole('button', { name: 'Despachar' }),
    ).toBeDisabled()
  })
})
