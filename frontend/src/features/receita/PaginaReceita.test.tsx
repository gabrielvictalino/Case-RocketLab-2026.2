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
import { afterEach, expect, it, vi } from 'vitest'
import { PaginaReceita } from './PaginaReceita'

const RequestNativo = globalThis.Request
class RequestCompativel extends RequestNativo {
  constructor(input: RequestInfo | URL, init?: RequestInit) {
    if (init?.signal) {
      const copia = { ...init }
      delete copia.signal
      super(input, copia)
    } else super(input, init)
  }
}
globalThis.Request = RequestCompativel
window.Request = RequestCompativel

const carga = {
  id: '1',
  batch_id: 'teste',
  versao_contrato: '0.2',
  sintetica: true,
  carregado_em: '2026-07-01T00:00:00Z',
  competencia_inicial: '2022-07-01',
  competencia_mais_recente: '2026-06-01',
}
const efeitos = { volume: '-10', reajuste: '20', bandeira: '5', mix: '5' }
const dados = {
  receita_base: '100',
  receita_atual: '120',
  variacao: '20',
  variacao_pct: '20',
  volume_base_kwh: '2000000',
  volume_atual_kwh: '1000000',
  variacao_volume_kwh: '-1000000',
  variacao_volume_pct: '-10.50',
  efeitos,
  periodo: '2025-07..2026-06',
  comparacao: '2024-07..2025-06',
  carga,
}
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
const urls: URL[] = []
function iniciar(
  opcao: 'normal' | 'erro' | 'comparacao' | 'invalido' | 'vazio' | 'zero' | 'negativo' = 'normal',
  url = '/receita?periodo=2025-07..2026-06&comparacao=2024-07..2025-06&classe=Residencial',
) {
  urls.length = 0
  vi.stubGlobal(
    'fetch',
    vi.fn(async (request: Request) => {
      const u = new URL(request.url)
      urls.push(u)
      if (u.pathname === '/api/v1/meta/carga') return json(carga)
      if (u.pathname === '/api/v1/meta/filtros')
        return json({
          municipios: ['Recife'],
          classes: ['Residencial'],
          bairros: {},
          alimentadores: [],
        })
      if (u.pathname.startsWith('/api/v1/receita/')) {
        if (opcao === 'comparacao')
          return json({ code: 'COMPARACAO_INDISPONIVEL', detail: 'Indisponível' }, 422)
        if (u.pathname.endsWith('/decomposicao')) return json(opcao === 'zero' ? { ...dados, variacao_pct: null, variacao: '0' } : opcao === 'negativo' ? { ...dados, variacao: '-20', variacao_pct: '-20' } : dados)
        if (u.pathname.endsWith('/locais'))
          return json({
            ...dados,
            total: opcao === 'zero' ? { ...dados, variacao: '0' } : opcao === 'negativo' ? { ...dados, variacao: '-20', variacao_pct: '-20' } : dados,
            itens: opcao === 'vazio' ? [] : [
              {
                ...dados,
                municipio: 'Recife',
                bairro: u.searchParams.get('nivel') === 'bairro' ? 'Boa Viagem' : null,
              },
            ],
          })
        if (u.pathname.endsWith('/grupos'))
          return opcao === 'erro'
            ? json({ detail: 'Falha', code: 'ERRO' }, 500)
            : json({
                ...dados,
                itens: ['DEMAIS', 'GD', 'IRREGULARIDADE_CONFIRMADA'].map(
                  (grupo_uc) => ({ ...dados, grupo_uc, volume_atual_kwh: opcao === 'invalido' ? 'NaN' : dados.volume_atual_kwh }),
                ),
              })
      }
      throw new Error(`URL inesperada: ${u.pathname}`)
    }),
  )
  const router = createMemoryRouter(
    [{ path: '/receita', element: <PaginaReceita /> }],
    { initialEntries: [url] },
  )
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})
it('mostra cascata e grupos, navega ao bairro, volta e preserva filtros', async () => {
  const router = iniciar()
  const tabela = await screen.findByRole('table', {
    name: 'Valores da cascata de receita',
  })
  expect(
    within(tabela)
      .getAllByRole('row')
      .map((r) => r.textContent),
  ).toEqual([
    'Receita jul/2024–jun/2025R$ 100,00',
    'Volume-R$ 10,00',
    'ReajusteR$ 20,00',
    'BandeiraR$ 5,00',
    'MixR$ 5,00',
    'Receita jul/2025–jun/2026R$ 120,00',
  ])
  expect(screen.getByText('Insight do período')).toBeVisible()
  expect((await screen.findAllByText('-10,5%')).length).toBeGreaterThan(0)
  fireEvent.click(await screen.findByRole('button', { name: 'Ver bairros de Recife' }))
  await screen.findByText('Boa Viagem')
  const params = new URLSearchParams(router.state.location.search)
  expect(params.get('municipio')).toBe('Recife')
  expect(params.get('classe')).toBe('Residencial')
  expect(params.get('periodo')).toBe('2025-07..2026-06')
  expect(params.get('comparacao')).toBe('2024-07..2025-06')
  await waitFor(() =>
    expect(
      urls.some(
        (u) =>
          u.pathname.endsWith('/locais') && u.searchParams.get('nivel') === 'bairro',
      ),
    ).toBe(true),
  )
  await act(async () => {
    await router.navigate(-1)
  })
  await screen.findByRole('button', { name: 'Ver bairros de Recife' })
  expect(new URLSearchParams(router.state.location.search).get('classe')).toBe(
    'Residencial',
  )
  // O insight da tela usa o mesmo período e os recortes dela.
  expect(
    urls.some(
      (u) =>
        u.pathname === '/api/v1/insights/receita' &&
        u.searchParams.get('periodo') === '2025-07..2026-06' &&
        u.searchParams.get('classe') === 'Residencial',
    ),
  ).toBe(true)
})
it('aplica município e classe sem enviar bairro ou alimentador', async () => {
  const router = iniciar(
    'normal',
    '/receita?periodo=2025-07..2026-06&comparacao=2024-07..2025-06&municipio=Recife&classe=Residencial&bairro=Pina&alimentador=ABC',
  )
  await screen.findByText('Boa Viagem')
  await waitFor(() =>
    expect(urls.filter((u) => u.pathname.startsWith('/api/v1/receita/'))).toHaveLength(
      3,
    ),
  )
  for (const u of urls.filter((u) => u.pathname.startsWith('/api/v1/receita/'))) {
    expect(u.searchParams.get('municipio')).toBe('Recife')
    expect(u.searchParams.get('classe')).toBe('Residencial')
    expect(u.searchParams.has('bairro')).toBe(false)
    expect(u.searchParams.has('alimentador')).toBe(false)
  }
  fireEvent.click(screen.getByRole('button', { name: 'Todos os municípios' }))
  expect(
    await screen.findByRole('button', { name: 'Ver bairros de Recife' }),
  ).toBeInTheDocument()
  const params = new URLSearchParams(router.state.location.search)
  expect(params.has('municipio')).toBe(false)
  expect(params.get('classe')).toBe('Residencial')
  expect(params.get('periodo')).toBe('2025-07..2026-06')
  expect(params.get('comparacao')).toBe('2024-07..2025-06')
})
it('isola erro de grupos e mostra comparação indisponível', async () => {
  iniciar('erro')
  expect(await screen.findByRole('alert')).toHaveTextContent('Falha')
  expect(
    screen.getByRole('table', { name: 'Valores da cascata de receita' }),
  ).toBeInTheDocument()
  cleanup()
  iniciar('comparacao')
  expect(
    await screen.findAllByText(
      'Sem período de comparação disponível para decompor a variação.',
    ),
  ).toHaveLength(3)
})

it('mostra legenda, grupos ordenados, cabeçalho e exportação indisponível', async () => {
  iniciar()
  const tabela = await screen.findByRole('table', { name: 'Volume por grupo de UC' })
  const linhas = within(tabela).getAllByRole('row')
  expect(linhas.slice(1).map((linha) => linha.textContent)).toEqual([
    expect.stringContaining('Com GD'), expect.stringContaining('Com irregularidade confirmada'), expect.stringContaining('Demais'),
  ])
  expect(within(tabela).queryByRole('columnheader', { name: 'UCs' })).not.toBeInTheDocument()
  expect(within(tabela).getAllByText('1,00')).toHaveLength(3)
  expect(await screen.findByText('Efeito que reduz')).toBeVisible()
  expect(screen.getByText('O eixo não começa em zero para tornar os efeitos legíveis.')).toBeVisible()
  expect(screen.getByText(/Receita faturada ·.*\+R\$/)).toBeVisible()
  expect(screen.getByRole('columnheader', { name: /Da alta total/ })).toBeVisible()
  expect(screen.getByRole('button', { name: 'Exportar' })).toBeDisabled()
})
it('isola resposta malformada e mostra locais vazios', async () => {
  iniciar('invalido')
  expect(await screen.findByRole('alert')).toHaveTextContent('Resposta de receita inválida')
  expect(screen.getByRole('table', { name: 'Valores da cascata de receita' })).toBeInTheDocument()
  expect(screen.getByRole('table', { name: 'Detalhamento por local' })).toBeInTheDocument()
  cleanup()
  iniciar('vazio')
  expect(await screen.findByText('Nenhum registro encontrado')).toBeInTheDocument()
})
it('trata variação total zero e comparação percentual nula', async () => {
  iniciar('zero')
  expect(await screen.findByRole('columnheader', { name: /Da variação total/ })).toBeInTheDocument()
  const tabela = screen.getByRole('table', { name: 'Detalhamento por local' })
  expect(within(tabela).getByText('—')).toBeVisible()
  expect(screen.getByText(/Receita faturada ·/).textContent).not.toContain('%')
})

it('mostra sinal negativo no cabeçalho e título de queda total', async () => {
  iniciar('negativo')
  expect(await screen.findByRole('columnheader', { name: /Da queda total/ })).toBeVisible()
  expect(screen.getByText(/Receita faturada ·/)).toHaveTextContent(/−R\$.*\(−20,0%\)/)
})
