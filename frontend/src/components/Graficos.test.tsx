import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import {
  ConteudoTooltipComparativo,
  GraficoBarrasComparativas,
  GraficoCascata,
  GraficoSerieComparativa,
  montarBarrasCascata,
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

it('calcula faixas, margem e eixo truncado inclusive ao cruzar zero', () => {
  const positivo = montarBarrasCascata([
    { rotulo: 'base', tipo: 'inicio', valor: 100 },
    { rotulo: 'queda', tipo: 'delta', valor: -20 },
    { rotulo: 'alta', tipo: 'delta', valor: 10 },
    { rotulo: 'fim', tipo: 'fim', valor: 90 },
  ])
  expect(positivo.barras.map((b) => b.faixa)).toEqual([[78, 100], [100, 80], [80, 90], [78, 90]])
  expect(positivo.dominio).toEqual([78, 102])
  expect(positivo.eixoTruncado).toBe(true)
  const cruzando = montarBarrasCascata([
    { rotulo: 'base', tipo: 'inicio', valor: 5 },
    { rotulo: 'queda', tipo: 'delta', valor: -10 },
    { rotulo: 'fim', tipo: 'fim', valor: -5 },
  ])
  expect(cruzando.barras[1]?.faixa).toEqual([5, -5])
  expect(cruzando.eixoTruncado).toBe(false)
  const zeros = montarBarrasCascata([{ rotulo: 'base', tipo: 'inicio', valor: 0 }, { rotulo: 'efeito', tipo: 'delta', valor: 0 }, { rotulo: 'fim', tipo: 'fim', valor: 0 }])
  expect(zeros.dominio).toEqual([0, 1])
  expect(zeros.eixoTruncado).toBe(false)
})

it('associa cada rótulo à própria barra, inclusive efeitos zero', () => {
  const passos = [
    { rotulo: 'Receita', detalhe: 'P0', valor: 343989.6, tipo: 'inicio' as const },
    { rotulo: 'Volume', valor: 476, tipo: 'delta' as const },
    { rotulo: 'Reajuste', valor: 0, tipo: 'delta' as const },
    { rotulo: 'Bandeira', valor: 3429, tipo: 'delta' as const },
    { rotulo: 'Mix', valor: 0, tipo: 'delta' as const },
    { rotulo: 'Receita', detalhe: 'P1', valor: 347894.6, tipo: 'fim' as const },
  ]
  const { barras } = montarBarrasCascata(passos, (valor, tipo) => `${tipo}:${valor}`)
  expect(barras.map((barra) => barra.rotuloValor)).toEqual([
    'inicio:343989.6', 'delta:476', 'delta:0', 'delta:3429', 'delta:0', 'fim:347894.6',
  ])
  expect(barras.map((barra) => barra.chaveEixo)).toEqual([
    'Receita · P0', 'Volume', 'Reajuste', 'Bandeira', 'Mix', 'Receita · P1',
  ])
})

it('exibe observacoes no tooltip comparativo', () => {
  const { rerender } = render(
    <ConteudoTooltipComparativo
      active
      label="jan/26"
      payload={[{ graphicalItemId: 'consumo-atual', dataKey: 'atual', name: 'Consumo', value: 150 }]}
      observacoes={{ 'jan/26': 'Troca de medidor: consumo estimado pela mediana da UC' }}
      formatarValor={(valor) => `${valor} kWh`}
    />,
  )

  expect(screen.getByText('jan/26')).toBeInTheDocument()
  expect(screen.getByText('Consumo: 150 kWh')).toBeInTheDocument()
  expect(screen.getByText('Troca de medidor: consumo estimado pela mediana da UC')).toBeInTheDocument()

  rerender(
    <ConteudoTooltipComparativo
      active
      label="fev/26"
      payload={[{ graphicalItemId: 'consumo-atual', dataKey: 'atual', name: 'Consumo', value: 120 }]}
      observacoes={{ 'fev/26': 'Leitura estimada' }}
    />,
  )

  expect(screen.getByText('Leitura estimada')).toBeInTheDocument()
})


it('renderiza marcadores diretamente nas barras do grafico', async () => {
  const ResizeObserverOriginal = globalThis.ResizeObserver

  class ResizeObserverSimulado implements ResizeObserver {
    observe() {
      this.callback(
        [{
          contentRect: {
            width: 800,
            height: 300,
            x: 0,
            y: 0,
            top: 0,
            left: 0,
            right: 800,
            bottom: 300,
            toJSON: () => ({}),
          },
        } as ResizeObserverEntry],
        this,
      )
    }

    unobserve() {}
    disconnect() {}

    constructor(
      private callback: ResizeObserverCallback,
    ) {}
  }

  globalThis.ResizeObserver = ResizeObserverSimulado

  try {
    const { container } = render(
      <GraficoBarrasComparativas
        dados={[
          { rotulo: 'jan/2026', atual: 180, comparacao: 150 },
          { rotulo: 'fev/2026', atual: 200, comparacao: 170 },
        ]}
        rotuloAtual="Consumo atual"
        rotuloComparacao="Ano anterior"
        marcadores={{
          'jan/2026': '\u25cf',
          'fev/2026': '\u25c6',
        }}
      />,
    )

    await waitFor(() => {
      const grafico = container.querySelector('svg.recharts-surface')
      expect(grafico).not.toBeNull()

      const rotulos = Array.from(
        grafico?.querySelectorAll('.recharts-cartesian-axis-tick-value') ?? [],
      ).map((elemento) => elemento.textContent)

      expect(rotulos).toContain('jan/2026 \u25cf')
      expect(rotulos).toContain('fev/2026 \u25c6')
    })
  } finally {
    globalThis.ResizeObserver = ResizeObserverOriginal
  }
})
