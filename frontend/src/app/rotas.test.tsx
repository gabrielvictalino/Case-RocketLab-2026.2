import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
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

const VISAO_UC_AMOSTRA = {
  id_uc: 'UC100123',
  data_referencia: null,
  cabecalho: {
    titular: 'Titular de teste',
    documento: '12345678901',
    classe: 'Residencial',
    endereco: 'Endereco de teste',
    municipio: 'Recife',
    bairro: 'Centro',
    alimentador: 'AL-01',
    medidor_atual: null,
    gd: null,
  },
  consumo: {
    competencia_inicial: '2025-07',
    competencia_final: '2026-06',
    meses: [],
  },
  faturas_abertas: [],
  interrupcoes: {
    ocorrencias: [],
    alimentador: { alimentador: 'AL-01', interrupcoes: 0, dec: 0 },
  },
  chamados: [],
  inspecoes: [],
  ordem_ativa: null,
  explicacao_conta: {
    situacao: 'SEM_FATURA',
    frase: 'Nao ha fatura para comparacao.',
    atual: null,
    anterior: null,
    variacao_valor: null,
    variacao_valor_pct: null,
    variacao_consumo_pct: null,
    efeitos: null,
  },
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
      const corpo = /\/api\/v1\/ucs\/UC\d{6}(?:\?|$)/.test(url)
        ? { ...VISAO_UC_AMOSTRA, id_uc: url.match(/UC\d{6}/)?.[0] ?? 'UC100123' }
        : url.includes('/api/v1/meta/filtros')
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

describe('criterios da tela UC', () => {
  it('abre diretamente uma UC pela URL e apresenta seus dados', async () => {
    renderizarRota('/ucs/UC100123')

    expect(await screen.findByText('Titular de teste')).toBeInTheDocument()
    expect(screen.getByRole('textbox', { name: 'Número da UC' })).toHaveValue('UC100123')
  })

  it('nao apresenta carregamento permanente sem UC selecionada', async () => {
    renderizarRota('/unidade-consumidora')

    expect(await screen.findByText('Busque uma unidade consumidora')).toBeInTheDocument()
    expect(screen.queryByLabelText('Carregando dados')).not.toBeInTheDocument()
  })

  it('mostra mensagem especifica para UC invalida na URL', async () => {
    renderizarRota('/ucs/INVALIDA')

    expect(await screen.findByText('Número de UC inválido')).toBeInTheDocument()
  })

  it('diferencia UC inexistente de falha do servidor', async () => {
    vi.stubGlobal('fetch', vi.fn(async (req: Request | string | URL) => {
      const url = typeof req === 'string' ? req : req instanceof URL ? req.href : req.url
      return new Response(JSON.stringify(url.includes('/api/v1/ucs/') ? { detail: 'UC não encontrada' } : CARGA_AMOSTRA), {
        status: url.includes('/api/v1/ucs/') ? 404 : 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }))

    renderizarRota('/ucs/UC100123')

    expect(await screen.findByText('Unidade consumidora não encontrada')).toBeInTheDocument()
  })

  it('oferece nova tentativa quando o servidor falha', async () => {
    vi.stubGlobal('fetch', vi.fn(async (req: Request | string | URL) => {
      const url = typeof req === 'string' ? req : req instanceof URL ? req.href : req.url
      return new Response(JSON.stringify(url.includes('/api/v1/ucs/') ? { detail: 'Falha temporária' } : CARGA_AMOSTRA), {
        status: url.includes('/api/v1/ucs/') ? 500 : 200,
        headers: { 'Content-Type': 'application/json' },
      })
    }))

    renderizarRota('/ucs/UC100123')

    expect(await screen.findByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument()
  })
})
describe('rotas do portal', () => {

  it('sincroniza a busca ao voltar e avancar entre unidades consumidoras', async () => {
    const { router } = renderizarRota('/unidade-consumidora')

    const campo = () => screen.getByRole('textbox', { name: 'N\u00famero da UC' })

    expect(await screen.findByRole('heading', {
      level: 1,
      name: 'Unidade Consumidora',
    })).toBeInTheDocument()

    fireEvent.change(campo(), { target: { value: '100123' } })
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => {
      expect(router.state.location.search).toContain('uc=UC100123')
      expect(campo()).toHaveValue('UC100123')
    })

    fireEvent.change(campo(), { target: { value: '100456' } })
    fireEvent.click(screen.getByRole('button', { name: 'Buscar' }))

    await waitFor(() => {
      expect(router.state.location.search).toContain('uc=UC100456')
      expect(campo()).toHaveValue('UC100456')
    })

    await act(async () => {
      await router.navigate(-1)
    })
    expect(campo()).toHaveValue('UC100123')

    await act(async () => {
      await router.navigate(1)
    })
    expect(campo()).toHaveValue('UC100456')
  })

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
    const nav = (await screen.findAllByRole('navigation')).find((elemento) => !elemento.hasAttribute('aria-label'))!
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
