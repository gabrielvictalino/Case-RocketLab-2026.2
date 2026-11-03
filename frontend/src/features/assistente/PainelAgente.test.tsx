import '@testing-library/jest-dom/vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { rotas } from '@/app/rotas'
import type { RespostaPergunta } from '@/features/assistente/conversa'
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

const RESPOSTA: RespostaPergunta = {
  tipo: 'resposta',
  texto: 'A receita faturada de Recife de jul/2025 a jun/2026 foi de R$ 1.234.567,89.',
  metrica: 'Receita faturada (R$)',
  filtros: ['município = Recife'],
  periodo: { inicio: '2025-07-01', fim: '2026-06-01', descricao: 'jul/2025 a jun/2026' },
  motivo: null,
  alternativa: null,
  consultas: [
    {
      sql_gerado: 'SELECT ...',
      sql_executado: 'SELECT round(sum(receita), 2) AS receita_reais FROM ai_read.receita_volume_mensal LIMIT 1000',
      colunas: ['receita_reais'],
      linhas: [[1234567.89]],
      total_linhas: 1,
      duracao_ms: 12,
      erro: null,
    },
  ],
  modelo: 'gemini-3.1-flash-lite',
  tokens_entrada: 1200,
  tokens_saida: 40,
  latencia_ms: 1830,
  id_resposta: '11111111-2222-3333-4444-555555555555',
  conversa_id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
}

const NAO_SEI: RespostaPergunta = {
  ...RESPOSTA,
  tipo: 'nao_sei',
  texto: 'Não sei. A base não tem a geração mensal das placas.',
  metrica: null,
  filtros: [],
  periodo: null,
  motivo: 'A base não tem a geração mensal das placas.',
  alternativa: 'Quantas UCs de Olinda têm painel solar?',
  consultas: [],
}

type Roteiro = (corpo: Record<string, unknown>) => Response | Promise<Response>

let roteiro: Roteiro
// Quando definida, /meta/carga espera esta promessa: a carga ainda não chegou.
let cargaAdiada: Promise<Response> | null = null
const perguntasEnviadas: Record<string, unknown>[] = []

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
    { access_token: 'token-agente', token_type: 'bearer', expires_in: 3600 },
    'comercial',
  )
  perguntasEnviadas.length = 0
  roteiro = () => json(RESPOSTA)
  cargaAdiada = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) => {
      if (req.url.includes('/api/v1/assistente/perguntas')) {
        const corpo = (await req.clone().json()) as Record<string, unknown>
        perguntasEnviadas.push(corpo)
        return roteiro(corpo)
      }
      if (req.url.includes('/api/v1/meta/filtros')) {
        return json(FILTROS)
      }
      if (req.url.includes('/api/v1/ordens-inspecao')) {
        return json({ items: [], total: 0, page: 1, size: 25 })
      }
      if (req.url.includes('/api/v1/meta/carga') && cargaAdiada) {
        return cargaAdiada
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

async function abrirPainel() {
  fireEvent.click(await screen.findByRole('button', { name: 'Perguntar ao agente' }))
  return screen.getByRole('dialog', { name: 'Pergunte aos dados' })
}

function perguntar(painel: HTMLElement, pergunta: string) {
  fireEvent.change(within(painel).getByLabelText('Pergunte sobre os dados'), {
    target: { value: pergunta },
  })
  fireEvent.click(within(painel).getByRole('button', { name: 'Enviar pergunta' }))
}

describe('PainelAgente', () => {
  it('mostra o contexto da tela e envia tela, período, comparação e recortes da URL', async () => {
    renderizarApp(
      '/receita?periodo=2025-07..2026-06&comparacao=2024-07..2025-06&municipio=Recife&classe=Residencial',
    )
    const painel = await abrirPainel()
    expect(
      await within(painel).findByText('Receita · jul/2025–jun/2026 × jul/2024–jun/2025'),
    ).toBeInTheDocument()
    expect(within(painel).getByText('Município: Recife')).toBeInTheDocument()

    perguntar(painel, 'Qual a receita?')

    await waitFor(() => expect(perguntasEnviadas).toHaveLength(1))
    expect(perguntasEnviadas[0]).toEqual({
      pergunta: 'Qual a receita?',
      conversa_id: null,
      contexto: {
        tela: 'receita',
        periodo: '2025-07..2026-06',
        comparacao: '2024-07..2025-06',
        recortes: { municipio: 'Recife', classe: 'Residencial' },
      },
    })
  })

  it('só envia a pergunta depois que o período da URL é resolvido', async () => {
    let liberarCarga: () => void = () => {}
    cargaAdiada = new Promise<Response>((resolve) => (liberarCarga = () => resolve(json(CARGA))))
    renderizarApp('/receita?periodo=2025-01..2025-06&comparacao=2024-01..2024-06')
    const painel = await abrirPainel()
    const campo = within(painel).getByLabelText('Pergunte sobre os dados')
    fireEvent.change(campo, { target: { value: 'Qual a receita?' } })

    // Nem o Enter, nem o botão, nem as sugestões mandam a pergunta sem o período.
    fireEvent.keyDown(campo, { key: 'Enter' })
    expect(within(painel).getByRole('button', { name: 'Enviar pergunta' })).toBeDisabled()
    const sugestao = within(painel).getByRole('button', {
      name: 'Quais os 5 alimentadores com o pior DEC no último ano?',
    })
    expect(sugestao).toBeDisabled()
    fireEvent.click(sugestao)
    expect(within(painel).getByRole('status')).toHaveTextContent('Carregando o período da tela')
    expect(perguntasEnviadas).toHaveLength(0)

    liberarCarga()
    await waitFor(() =>
      expect(within(painel).getByRole('button', { name: 'Enviar pergunta' })).toBeEnabled(),
    )
    fireEvent.keyDown(campo, { key: 'Enter' })
    await waitFor(() => expect(perguntasEnviadas).toHaveLength(1))
    expect(perguntasEnviadas[0]?.contexto).toMatchObject({
      periodo: '2025-01..2025-06',
      comparacao: '2024-01..2024-06',
    })
  })

  it('mostra as etapas enquanto espera e depois a resposta com chips e o SQL', async () => {
    let responder: (resposta: Response) => void = () => {}
    roteiro = () => new Promise<Response>((resolve) => (responder = resolve))
    renderizarApp('/receita?periodo=2025-07..2026-06&comparacao=2024-07..2025-06')
    const painel = await abrirPainel()

    perguntar(painel, 'Qual a receita de Recife?')

    const etapas = await within(painel).findByRole('status', { name: 'Andamento da resposta' })
    expect(within(etapas).getByText('Entendendo a pergunta')).toHaveAttribute('aria-current', 'step')
    expect(within(etapas).getByText('Consultando os dados')).toBeInTheDocument()
    expect(within(etapas).getByText('Redigindo')).toBeInTheDocument()
    expect(within(painel).getByRole('button', { name: 'Enviar pergunta' })).toBeDisabled()

    responder(json(RESPOSTA))

    expect(await within(painel).findByText(RESPOSTA.texto)).toBeInTheDocument()
    expect(within(painel).getByText('Período: jul/2025 a jun/2026')).toBeInTheDocument()
    expect(within(painel).getByText('Métrica: Receita faturada (R$)')).toBeInTheDocument()
    expect(within(painel).getByText('município = Recife')).toBeInTheDocument()

    const comoCheguei = within(painel).getByText('Como cheguei a esta resposta')
    fireEvent.click(comoCheguei)
    const detalhes = comoCheguei.closest('details') as HTMLElement
    expect(within(detalhes).getByText(/FROM ai_read\.receita_volume_mensal/)).toBeInTheDocument()
    expect(within(detalhes).getByRole('columnheader', { name: 'receita_reais' })).toBeInTheDocument()
    expect(within(detalhes).getByRole('cell', { name: '1.234.567,89' })).toBeInTheDocument()
    expect(within(detalhes).getByText('1 linha')).toBeInTheDocument()
  })

  it('mostra o cartão de não sei com motivo e alternativa, que vira pergunta', async () => {
    roteiro = () => json(NAO_SEI)
    renderizarApp('/visao-geral')
    const painel = await abrirPainel()

    perguntar(painel, 'Quanto as placas geraram em jun/2026?')

    expect(
      await within(painel).findByText('Não sei responder com os dados disponíveis'),
    ).toBeInTheDocument()
    expect(within(painel).getByText(NAO_SEI.motivo as string)).toBeInTheDocument()

    roteiro = () => json(RESPOSTA)
    fireEvent.click(within(painel).getByRole('button', { name: NAO_SEI.alternativa as string }))
    await waitFor(() => expect(perguntasEnviadas).toHaveLength(2))
    expect(perguntasEnviadas[1]).toMatchObject({
      pergunta: NAO_SEI.alternativa,
      conversa_id: NAO_SEI.conversa_id,
    })
  })

  it.each([
    [
      429,
      'LIMITE_DE_PERGUNTAS',
      'Limite de 20 perguntas por minuto atingido. Tente de novo em 12 s.',
      'Limite de 20 perguntas por minuto atingido. Tente de novo em 12 s.',
    ],
    [
      429,
      'COTA_DE_TOKENS_ESGOTADA',
      'A cota diária acabou.',
      'A cota diária do assistente acabou. Ela volta à meia-noite.',
    ],
    [
      503,
      'PROVEDOR_INDISPONIVEL',
      'O provedor do modelo está indisponível',
      'O provedor do modelo de IA está fora do ar. Tente de novo em instantes.',
    ],
    [
      503,
      'ASSISTENTE_INDISPONIVEL',
      'Assistente não configurado neste ambiente',
      'O assistente não está configurado neste ambiente.',
    ],
  ])('mostra a mensagem própria do erro %i %s', async (status, code, detail, mensagem) => {
    roteiro = () => json({ detail, code }, status)
    renderizarApp('/receita')
    const painel = await abrirPainel()

    perguntar(painel, 'Qual a receita?')

    expect(await within(painel).findByRole('alert')).toHaveTextContent(mensagem)
    expect(within(painel).getByLabelText('Pergunte sobre os dados')).toBeEnabled()
  })

  it('mantém a conversa ao trocar de tela e manda o follow-up na mesma conversa', async () => {
    const router = renderizarApp('/receita?periodo=2025-07..2026-06')
    let painel = await abrirPainel()
    perguntar(painel, 'Qual a receita de Recife?')
    expect(await within(painel).findByText(RESPOSTA.texto)).toBeInTheDocument()

    fireEvent.click(within(painel).getByRole('button', { name: 'Fechar painel do agente' }))
    await router.navigate('/operacao?periodo=2025-07..2026-06')
    painel = await abrirPainel()

    expect(within(painel).getByText('Qual a receita de Recife?')).toBeInTheDocument()
    expect(within(painel).getByText(RESPOSTA.texto)).toBeInTheDocument()
    expect(await within(painel).findByText(/^Operação ·/)).toBeInTheDocument()

    perguntar(painel, 'E em Olinda?')
    await waitFor(() => expect(perguntasEnviadas).toHaveLength(2))
    expect(perguntasEnviadas[1]).toMatchObject({
      pergunta: 'E em Olinda?',
      conversa_id: RESPOSTA.conversa_id,
      contexto: { tela: 'operacao' },
    })

    fireEvent.click(within(painel).getByRole('button', { name: 'Começar uma nova conversa' }))
    expect(within(painel).queryByText('Qual a receita de Recife?')).not.toBeInTheDocument()
  })

  it('envia o id da UC aberta na tela Unidade Consumidora', async () => {
    renderizarApp('/unidade-consumidora?uc=UC000123')
    const painel = await abrirPainel()
    perguntar(painel, 'Quanto essa UC consumiu?')
    await waitFor(() => expect(perguntasEnviadas).toHaveLength(1))
    expect(perguntasEnviadas[0]).toMatchObject({
      contexto: { tela: 'unidade-consumidora', recortes: { id_uc: 'UC000123' } },
    })
  })
})
