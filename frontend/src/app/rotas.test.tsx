import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
import { rotas } from '@/app/rotas'

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

afterEach(() => {
  cleanup()
})

function renderizarRota(caminhoInicial: string) {
  const router = createMemoryRouter(rotas, {
    initialEntries: [caminhoInicial],
  })
  return render(<RouterProvider router={router} />)
}

describe('rotas do portal', () => {
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
    expect(screen.getByText('Em construção')).toBeInTheDocument()
  })

  it('lista os 5 links na navegação lateral e marca a rota ativa', async () => {
    renderizarRota('/receita')
    const nav = await screen.findByRole('navigation')
    const links = nav.querySelectorAll('a')
    expect(links).toHaveLength(5)

    expect(screen.getByRole('link', { name: 'Visão Geral' })).toHaveAttribute(
      'href',
      '/visao-geral',
    )
    expect(screen.getByRole('link', { name: 'Receita' })).toHaveAttribute(
      'href',
      '/receita',
    )
    expect(
      screen.getByRole('link', { name: 'Unidade Consumidora' }),
    ).toHaveAttribute('href', '/unidade-consumidora')
    expect(screen.getByRole('link', { name: 'Perdas' })).toHaveAttribute(
      'href',
      '/perdas',
    )
    expect(screen.getByRole('link', { name: 'Operação' })).toHaveAttribute(
      'href',
      '/operacao',
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
