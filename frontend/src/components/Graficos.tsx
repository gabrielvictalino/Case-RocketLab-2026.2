import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { EstadoIndisponivel } from '@/components/Estados'

export interface PontoSerieComparativa {
  rotulo: string
  atual: number | null
  comparacao?: number | null
}

export interface GraficoSerieComparativaProps {
  dados: PontoSerieComparativa[]
  rotuloAtual: string
  rotuloComparacao?: string
  corAtual?: 'data-1' | 'data-2'
  altura?: number
  indisponivel?: boolean
}

export function GraficoSerieComparativa({
  dados,
  rotuloAtual,
  rotuloComparacao,
  corAtual = 'data-1',
  altura = 220,
  indisponivel = false,
}: GraficoSerieComparativaProps) {
  if (indisponivel) {
    return <EstadoIndisponivel compacto />
  }

  const strokeAtual =
    corAtual === 'data-2' ? 'var(--data-2)' : 'var(--data-1)'

  return (
    <div className="ve-chart" style={{ height: `${altura}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={dados}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="rotulo" stroke="var(--ink-muted)" fontSize={11} />
          <YAxis stroke="var(--ink-muted)" fontSize={11} />
          <Tooltip />
          {rotuloComparacao && (
            <Line
              type="monotone"
              dataKey="comparacao"
              name={rotuloComparacao}
              stroke="var(--data-compare)"
              strokeWidth={1.75}
              dot={false}
            />
          )}
          <Line
            type="monotone"
            dataKey="atual"
            name={rotuloAtual}
            stroke={strokeAtual}
            strokeWidth={2}
            dot={{ r: 3 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

export interface GraficoBarrasComparativasProps {
  dados: PontoSerieComparativa[]
  rotuloAtual: string
  rotuloComparacao?: string
  corAtual?: 'data-1' | 'data-2'
  altura?: number
  indisponivel?: boolean
}

export function GraficoBarrasComparativas({
  dados,
  rotuloAtual,
  rotuloComparacao,
  corAtual = 'data-2',
  altura = 200,
  indisponivel = false,
}: GraficoBarrasComparativasProps) {
  if (indisponivel) {
    return <EstadoIndisponivel compacto />
  }

  const fillAtual = corAtual === 'data-1' ? 'var(--data-1)' : 'var(--data-2)'

  return (
    <div className="ve-chart" style={{ height: `${altura}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={dados}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="rotulo" stroke="var(--ink-muted)" fontSize={11} />
          <YAxis stroke="var(--ink-muted)" fontSize={11} />
          <Tooltip />
          <Bar dataKey="atual" name={rotuloAtual} fill={fillAtual} />
          {rotuloComparacao && (
            <Bar
              dataKey="comparacao"
              name={rotuloComparacao}
              fill="var(--data-compare)"
            />
          )}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export interface PassoCascata {
  rotulo: string
  valor: number
  tipo: 'inicio' | 'delta' | 'fim'
}

export interface GraficoCascataProps {
  passos: PassoCascata[]
  altura?: number
  indisponivel?: boolean
}

export function GraficoCascata({
  passos,
  altura = 240,
  indisponivel = false,
}: GraficoCascataProps) {
  if (indisponivel) {
    return <EstadoIndisponivel compacto />
  }

  return (
    <div className="ve-chart" style={{ height: `${altura}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={passos}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="rotulo" stroke="var(--ink-muted)" fontSize={11} />
          <YAxis stroke="var(--ink-muted)" fontSize={11} />
          <Tooltip />
          <Bar dataKey="valor">
            {passos.map((p, idx) => {
              const cor =
                p.tipo === 'inicio'
                  ? 'var(--data-compare)'
                  : p.tipo === 'fim'
                    ? 'var(--data-1)'
                    : p.valor >= 0
                      ? 'var(--favorable)'
                      : 'var(--unfavorable)'
              return <Cell key={idx} fill={cor} />
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
