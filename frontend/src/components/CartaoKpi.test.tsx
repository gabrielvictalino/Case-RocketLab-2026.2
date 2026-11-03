import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router'
import { CartaoKpi } from '@/components/CartaoKpi'

afterEach(() => {
  cleanup()
})

describe('CartaoKpi', () => {
  it('aplica classe favorável e crítica conforme sentidoFavoravel alta vs baixa', () => {
    const { rerender } = render(
      <CartaoKpi
        rotulo="Receita faturada"
        valor="R$ 100,00"
        variacao={0.076}
        sentidoFavoravel="alta"
      />,
    )
    const chipAltaPositiva = screen.getByText(/\+7,6%/).closest('.ve-delta')
    expect(chipAltaPositiva).toHaveClass('ve-delta-favorable')

    rerender(
      <CartaoKpi
        rotulo="Receita faturada"
        valor="R$ 100,00"
        variacao={-0.042}
        sentidoFavoravel="alta"
      />,
    )
    const chipAltaNegativa = screen.getByText(/-4,2%/).closest('.ve-delta')
    expect(chipAltaNegativa).toHaveClass('ve-delta-critical')

    rerender(
      <CartaoKpi
        rotulo="Inadimplência"
        valor="6,0%"
        variacao={-0.8}
        tipoVariacao="pp"
        sentidoFavoravel="baixa"
      />,
    )
    const chipBaixaNegativa = screen
      .getByText(/-0,8\s*p\.p\./)
      .closest('.ve-delta')
    expect(chipBaixaNegativa).toHaveClass('ve-delta-favorable')

    rerender(
      <CartaoKpi
        rotulo="FEC"
        valor="5,00"
        unidade="vezes"
        variacao={0.032}
        sentidoFavoravel="baixa"
      />,
    )
    const chipBaixaPositiva = screen.getByText(/\+3,2%/).closest('.ve-delta')
    expect(chipBaixaPositiva).toHaveClass('ve-delta-critical')
  })

  it('exibe estado indisponível sem números quando indisponivel=true', () => {
    render(<CartaoKpi rotulo="Tarifa média" unidade="/MWh" indisponivel />)
    expect(
      screen.getByText('Dados ainda não disponíveis nesta versão do portal.'),
    ).toBeInTheDocument()
  })

  it('mostra neutralidade, carregamento, ausência em par e link acessível', () => {
    const { rerender } = render(
      <CartaoKpi rotulo="Teste" valor="10" variacao={0.1} sentidoFavoravel="neutro" />,
    )
    expect(screen.getByText(/10,0%/).closest('.ve-delta')).toHaveClass('ve-delta-neutral')
    rerender(<CartaoKpi rotulo="Teste" carregando />)
    expect(screen.getByLabelText('Carregando dados')).toBeInTheDocument()
    rerender(
      <MemoryRouter>
        <CartaoKpi
          rotulo="Teste"
          destino="/receita"
          semPeriodoComparacao
          pares={[{ subrotulo: 'A', semDados: true }, { subrotulo: 'B', valor: '0' }]}
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Teste · ver detalhe' }))
      .toHaveAttribute('href', '/receita')
    expect(screen.getByRole('link', { name: 'Teste · ver detalhe' }))
      .toHaveAccessibleDescription(/0/)
    expect(screen.getByText('Sem dados no período')).toBeInTheDocument()
    expect(screen.getByText('Sem período de comparação')).toBeInTheDocument()
    expect(screen.getByText('0')).toBeInTheDocument()
  })
})
