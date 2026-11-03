import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { Atendimentos, Faturas, GraficoConsumo } from './SecoesUnidadeConsumidora'

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


describe('Faturas - regressao', () => {
  it('nao apresenta fatura com atraso desconhecido como em dia', () => {
    render(
      <Faturas
        dados={[
          {
            id: 'fatura-1',
            competencia: 'jun/2026',
            vencimento: '10/07/2026',
            valor: 150,
            diasAtraso: null,
          },
        ]}
      />,
    )

    expect(screen.getByText('Atraso n\u00e3o informado')).toBeInTheDocument()
    expect(screen.queryByText('Em dia')).not.toBeInTheDocument()
  })

  it('diferencia faturas em dia e atrasadas', () => {
    render(
      <Faturas
        dados={[
          {
            id: 'fatura-1',
            competencia: 'jun/2026',
            vencimento: '10/07/2026',
            valor: 150,
            diasAtraso: 0,
          },
          {
            id: 'fatura-2',
            competencia: 'mai/2026',
            vencimento: '10/06/2026',
            valor: 200,
            diasAtraso: 12,
          },
        ]}
      />,
    )

    expect(screen.getByText('Em dia')).toBeInTheDocument()
    expect(screen.getByText('12 dias')).toBeInTheDocument()
  })
})

describe('Atendimentos - regressao', () => {
  it('mostra nao avaliou quando a nota e nula', () => {
    render(
      <Atendimentos
        dados={[
          {
            id: 'atendimento-1',
            titulo: 'Solicitacao de atendimento',
            protocolo: 'PROTO-001',
            abertura: '15/06/2026 11:30',
            status: 'CONCLUIDO',
            avaliacao: null,
            historico: [],
          },
        ]}
      />,
    )

    expect(screen.getByText(/N\u00e3o avaliou/)).toBeInTheDocument()
    expect(screen.queryByText(/Avalia\u00e7\u00e3o.*\/5/)).not.toBeInTheDocument()
  })
})
