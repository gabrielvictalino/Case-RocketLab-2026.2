
import '@testing-library/jest-dom/vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, describe, expect, it } from 'vitest'
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


afterEach(() => {
  cleanup()
})

function renderizarOperacao(caminho = '/operacao') {
  const router = createMemoryRouter(
    [
      {
        path: '/operacao',
        element: <PaginaOperacao />,
      },
    ],
    { initialEntries: [caminho] },
  )

  render(<RouterProvider router={router} />)

  return router
}

describe('Tela Operação', () => {
  it('exibe os indicadores e o aviso regulatório', () => {
    renderizarOperacao()

    expect(
      screen.getByRole('heading', { name: 'Operação' }),
    ).toBeInTheDocument()

    expect(
      screen.getByText(/limites regulatórios da ANEEL/),
    ).toBeInTheDocument()

    expect(
      screen.getByRole('heading', { name: 'Ranking de alimentadores' }),
    ).toBeInTheDocument()
  })

  it('inicia com eventos atípicos incluídos e CHI como padrão', () => {
    renderizarOperacao()

    expect(
      screen.getByRole('checkbox', {
        name: 'Incluir eventos atípicos',
      }),
    ).toBeChecked()

    expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
  })

  it('atualiza o filtro de eventos atípicos na URL', () => {
    const router = renderizarOperacao()

    fireEvent.click(
      screen.getByRole('checkbox', {
        name: 'Incluir eventos atípicos',
      }),
    )

    expect(router.state.location.search).toContain('atipicos=false')
  })

  it('atualiza a ordenação na URL', () => {
    const router = renderizarOperacao()

    fireEvent.change(screen.getByLabelText('Ordenar por'), {
      target: { value: 'fec' },
    })

    expect(router.state.location.search).toContain('ordenar=fec')
  })

  it('restaura os filtros padrão', () => {
    const router = renderizarOperacao(
      '/operacao?atipicos=false&ordenar=dec',
    )

    fireEvent.click(
      screen.getByRole('button', { name: 'Limpar filtros' }),
    )

    expect(router.state.location.search).toBe('')

    expect(
      screen.getByRole('checkbox', {
        name: 'Incluir eventos atípicos',
      }),
    ).toBeChecked()

    expect(screen.getByLabelText('Ordenar por')).toHaveValue('chi')
  })

  it('mantém filtros dependentes da API desabilitados', () => {
    renderizarOperacao()

    expect(screen.getByLabelText('Município')).toBeDisabled()
    expect(screen.getByLabelText('Alimentador')).toBeDisabled()
  })
})
