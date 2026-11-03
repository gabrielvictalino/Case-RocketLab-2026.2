import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import {
  GraficoBarrasComparativas,
  GraficoCascata,
  GraficoSerieComparativa,
} from '@/components/Graficos'

afterEach(() => {
  cleanup()
})

describe('Wrappers de gráficos Recharts', () => {
  it('renderiza containers dos 3 gráficos com fixtures e estado indisponível', () => {
    const { container, rerender } = render(
      <div>
        <GraficoSerieComparativa
          dados={[{ rotulo: 'jan/26', atual: 10, comparacao: 8 }]}
          rotuloAtual="Atual"
          rotuloComparacao="Anterior"
        />
        <GraficoBarrasComparativas
          dados={[{ rotulo: 'jan/26', atual: 100, comparacao: 90 }]}
          rotuloAtual="Volume 2026"
          rotuloComparacao="Volume 2025"
        />
        <GraficoCascata
          passos={[
            { rotulo: 'Início', valor: 100, tipo: 'inicio' },
            { rotulo: 'Reajuste', valor: 20, tipo: 'delta' },
            { rotulo: 'Fim', valor: 120, tipo: 'fim' },
          ]}
        />
      </div>,
    )

    expect(container.querySelectorAll('.ve-chart')).toHaveLength(3)

    rerender(
      <GraficoSerieComparativa
        dados={[]}
        rotuloAtual="Atual"
        indisponivel
      />,
    )
    expect(
      screen.getByText('Dados ainda não disponíveis nesta versão do portal.'),
    ).toBeInTheDocument()
  })
})
