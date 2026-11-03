import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { GraficoConsumo } from './SecoesUnidadeConsumidora'

afterEach(() => {
  cleanup()
})

describe('GraficoConsumo', () => {
  it('exibe os dois indicadores quando ha leitura estimada e troca de medidor', () => {
    render(
      <GraficoConsumo
        dados={[
          {
            competencia: '10/2026',
            consumoKwh: 180,
            consumoAnoAnteriorKwh: 150,
            estimado: true,
            trocaMedidor: true,
          },
        ]}
      />,
    )

    const grafico = screen.getByRole('img', {
      name: 'Gráfico de consumo mensal comparado ao ano anterior',
    })

    expect(grafico).toBeInTheDocument()
    expect(screen.getByText('● Leitura estimada')).toBeInTheDocument()
    expect(screen.getByText('◆ Troca de medidor')).toBeInTheDocument()
    expect(screen.getAllByText(/Troca de medidor: consumo estimado pela mediana da UC/)).toHaveLength(2)
  })
})
