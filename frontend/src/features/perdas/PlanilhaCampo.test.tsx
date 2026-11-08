import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { PlanilhaCampo } from './PlanilhaCampo'

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

const previa = {
  id: 'imp-1',
  arquivo: 'junho.xlsx',
  validas: [{ linha: 2 }, { linha: 3 }],
  erros: [{ linha: 4, motivo: 'Ordem já concluída' }],
  avisos: [{ linha: 3, motivo: 'Tipo fora dos 5 tipos da base: BYPASS' }],
}
const confirmada = {
  id: 'imp-1',
  arquivo: 'junho.xlsx',
  atualizadas: 2,
  rejeitadas: [],
  confirmado_em: '2026-11-08T12:00:00Z',
}
let ultima: unknown = null
let respostaEnvio: { status: number; corpo: unknown } = { status: 201, corpo: previa }
let respostaConfirmar: { status: number; corpo: unknown } = { status: 200, corpo: confirmada }
let chamadas: string[] = []
const json = (corpo: unknown, status = 200) =>
  new Response(JSON.stringify(corpo), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

beforeEach(() => {
  ultima = null
  respostaEnvio = { status: 201, corpo: previa }
  respostaConfirmar = { status: 200, corpo: confirmada }
  chamadas = []
  URL.createObjectURL = vi.fn(() => 'blob:planilha')
  URL.revokeObjectURL = vi.fn()
  vi.stubGlobal(
    'fetch',
    vi.fn(async (req: Request) => {
      const { pathname } = new URL(req.url)
      chamadas.push(`${req.method} ${pathname}`)
      if (pathname.endsWith('/importacoes/ultima')) return json(ultima)
      if (pathname.endsWith('/export')) return new Response(new Blob(['xlsx']))
      if (pathname.endsWith('/confirmar'))
        return json(respostaConfirmar.corpo, respostaConfirmar.status)
      return json(respostaEnvio.corpo, respostaEnvio.status)
    }),
  )
})
afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

function montar(podeEscrever = true) {
  const cliente = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const invalidar = vi.spyOn(cliente, 'invalidateQueries')
  render(
    <QueryClientProvider client={cliente}>
      <PlanilhaCampo podeEscrever={podeEscrever} />
    </QueryClientProvider>,
  )
  return { invalidar }
}
const escolherArquivo = () =>
  fireEvent.change(screen.getByLabelText('Arquivo da planilha de campo'), {
    target: { files: [new File(['x'], 'junho.xlsx')] },
  })

it('mostra a prévia com contagens, erros e avisos antes de confirmar', async () => {
  montar()
  escolherArquivo()
  expect(await screen.findByRole('dialog')).toHaveTextContent(
    'junho.xlsx: 2 linhas válidas · 1 linha com erro',
  )
  expect(screen.getByText('Linha 4: Ordem já concluída')).toBeVisible()
  expect(screen.getByText('Linha 3: Tipo fora dos 5 tipos da base: BYPASS')).toBeVisible()
  expect(chamadas.filter((chamada) => chamada.endsWith('/confirmar'))).toEqual([])
})

it('confirma, atualiza as telas e mostra o resumo', async () => {
  const { invalidar } = montar()
  escolherArquivo()
  fireEvent.click(await screen.findByRole('button', { name: 'Confirmar 2 linhas' }))
  expect(await screen.findByRole('status')).toHaveTextContent(
    'junho.xlsx: 2 ordens atualizadas.',
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(chamadas).toContain('POST /api/v1/ordens-inspecao/importacoes/imp-1/confirmar')
  await waitFor(() =>
    expect(invalidar.mock.calls.map(([filtro]) => filtro?.queryKey?.[0])).toEqual(
      expect.arrayContaining(['perdas-fila', 'ordens-inspecao', 'kpis', 'importacao-ultima']),
    ),
  )
})

it('não confirma uma prévia sem linhas válidas', async () => {
  respostaEnvio = { status: 201, corpo: { ...previa, validas: [], avisos: [] } }
  montar()
  escolherArquivo()
  expect(await screen.findByRole('button', { name: 'Confirmar 0 linhas' })).toBeDisabled()
})

it('voltar descarta a prévia sem aplicar nada', async () => {
  montar()
  escolherArquivo()
  fireEvent.click(await screen.findByRole('button', { name: 'Voltar' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(chamadas.filter((chamada) => chamada.endsWith('/confirmar'))).toEqual([])
})

it('mostra o motivo de um arquivo recusado', async () => {
  respostaEnvio = {
    status: 422,
    corpo: { detail: 'Faltam colunas na planilha: id_ordem', code: 'PLANILHA_INVALIDA' },
  }
  montar()
  escolherArquivo()
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'Faltam colunas na planilha: id_ordem',
  )
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('mantém a prévia aberta quando a confirmação é recusada', async () => {
  respostaConfirmar = {
    status: 409,
    corpo: { detail: 'Esta importação já foi confirmada', code: 'IMPORTACAO_JA_CONFIRMADA' },
  }
  montar()
  escolherArquivo()
  fireEvent.click(await screen.findByRole('button', { name: 'Confirmar 2 linhas' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Esta importação já foi confirmada')
  expect(screen.getByRole('dialog')).toBeVisible()
})

it('mostra a última importação', async () => {
  ultima = { ...confirmada, atualizadas: 1 }
  montar()
  expect(
    await screen.findByText('Última importação: junho.xlsx · 1 ordem atualizada'),
  ).toBeVisible()
})

it('exporta a planilha de campo', async () => {
  montar()
  fireEvent.click(screen.getByRole('button', { name: 'Exportar planilha de campo' }))
  await waitFor(() => expect(URL.createObjectURL).toHaveBeenCalled())
  expect(chamadas).toContain('GET /api/v1/ordens-inspecao/export')
})

it('só o cargo Perdas importa, mas todos exportam', () => {
  montar(false)
  expect(screen.getByRole('button', { name: 'Importar planilha de campo' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Exportar planilha de campo' })).toBeEnabled()
})
