import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { TooltipContentProps } from 'recharts'
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
  formatarValor?: (valor: number) => string
}

export function GraficoSerieComparativa({
  dados,
  rotuloAtual,
  rotuloComparacao,
  corAtual = 'data-1',
  altura = 220,
  indisponivel = false,
  formatarValor,
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
          <YAxis stroke="var(--ink-muted)" fontSize={11} tickFormatter={formatarValor} />
          <Tooltip formatter={formatarValor ? (valor) => formatarValor(Number(valor)) : undefined} />
          {rotuloComparacao && (
            <Line
              type="monotone"
              dataKey="comparacao"
              name={rotuloComparacao}
              stroke="var(--data-compare)"
              strokeWidth={1.75}
              dot={{ r: 2 }}
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

export function ConteudoTooltipComparativo({
  active,
  payload,
  label,
  observacoes,
  formatarValor,
}: {
  active?: boolean
  payload?: TooltipContentProps<number | string, string | number>["payload"]
  label?: string | number
  observacoes: Record<string, string>
  formatarValor?: (valor: number) => string
}) {
  if (!active || !payload?.length) return null

  const observacao = observacoes[String(label)]

  return (
    <div className="rounded-md border bg-background p-3 text-sm shadow-md">
      <p className="mb-1 font-medium">{String(label)}</p>
      {payload.map((item, indice) => (
        <p key={`${item.dataKey}-${indice}`}>
          {item.name}: {formatarValor ? formatarValor(Number(item.value)) : item.value}
        </p>
      ))}
      {observacao && <p className="mt-2 text-muted-foreground">{observacao}</p>}
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
  formatarValor?: (valor: number) => string
  observacoes?: Record<string, string>
}

export function GraficoBarrasComparativas({
  dados,
  rotuloAtual,
  rotuloComparacao,
  corAtual = 'data-2',
  altura = 200,
  indisponivel = false,
  formatarValor,
  observacoes,
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
          <YAxis stroke="var(--ink-muted)" fontSize={11} tickFormatter={formatarValor} />
          <Tooltip
            formatter={formatarValor ? (valor) => formatarValor(Number(valor)) : undefined}
            content={observacoes ? (props) => (
              <ConteudoTooltipComparativo
                active={props.active}
                payload={props.payload}
                label={props.label}
                observacoes={observacoes}
                formatarValor={formatarValor}
              />
            ) : undefined}
          />
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
  detalhe?: string
  valor: number
  tipo: 'inicio' | 'delta' | 'fim'
}

export interface GraficoCascataProps {
  passos: PassoCascata[]
  altura?: number
  indisponivel?: boolean
  formatarValor?: (valor: number) => string
  formatarEixo?: (valor: number) => string
  ticksEixo?: number[]
  formatarRotulo?: (valor: number, tipo: PassoCascata['tipo']) => string
}

// eslint-disable-next-line react-refresh/only-export-components
export function montarBarrasCascata(
  passos: PassoCascata[],
  formatarRotulo: (valor: number, tipo: PassoCascata['tipo']) => string = String,
) {
  let acumulado = 0
  const barras = passos.map((p) => {
    const inicio = p.tipo === 'delta' ? acumulado : p.valor
    const fim = p.tipo === 'delta' ? acumulado + p.valor : p.valor
    if (p.tipo !== 'fim') acumulado = fim
    return { ...p, inicio, fim, rotuloValor: formatarRotulo(p.valor, p.tipo), chaveEixo: [p.rotulo, p.detalhe].filter(Boolean).join(' · ') }
  })
  const niveis = barras.flatMap((b) => [b.inicio, b.fim])
  const menor = niveis.length ? Math.min(...niveis) : 0
  const maior = niveis.length ? Math.max(...niveis) : 0
  const margem =
    maior === menor ? Math.max(Math.abs(maior) * 0.1, 1) : (maior - menor) * 0.1
  const piso = menor >= 0 ? Math.max(0, menor - margem) : menor - margem
  const teto = maior + margem
  return {
    barras: barras.map((b) => ({
      ...b,
      faixa: [b.tipo === 'delta' ? b.inicio : piso, b.fim] as [number, number],
    })),
    dominio: [piso, teto] as [number, number],
    eixoTruncado: piso > 0,
  }
}

function corPasso(passo: PassoCascata): string {
  if (passo.tipo === 'inicio') return 'var(--data-compare)'
  if (passo.tipo === 'fim') return 'var(--data-1)'
  return passo.valor >= 0 ? 'var(--favorable)' : 'var(--unfavorable)'
}

export function GraficoCascata({
  passos,
  altura = 240,
  indisponivel = false,
  formatarValor = String,
  formatarEixo = formatarValor,
  ticksEixo,
  formatarRotulo = formatarValor,
}: GraficoCascataProps) {
  if (indisponivel) return <EstadoIndisponivel compacto />
  const { barras, dominio } = montarBarrasCascata(passos, formatarRotulo)
  return (
    <div>
      <table className="ve-sr">
        <caption>Valores da cascata de receita</caption>
        <tbody>
          {passos.map((p, i) => (
            <tr key={i}>
              <th scope="row">{p.rotulo}{p.detalhe ? ` ${p.detalhe}` : ''}</th>
              <td>{formatarValor(p.valor)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ve-chart" style={{ height: `${altura}px` }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={barras} margin={{ top: 24 }}>
          <CartesianGrid stroke="var(--chart-grid)" vertical={false} />
          <XAxis dataKey="chaveEixo" stroke="var(--ink-muted)" fontSize={11} height={45}
            tick={({ x, y, payload }) => {
              const barra = barras.find((item) => item.chaveEixo === payload.value)
              return (
                <text x={x} y={Number(y) + 12} textAnchor="middle" fill="var(--ink-muted)" fontSize={11}>
                  <tspan x={x}>{barra?.rotulo}</tspan>
                  <tspan x={x} dy="14">{barra?.detalhe}</tspan>
                </text>
              )
            }} />
          <YAxis
            domain={dominio}
            width={88}
            ticks={ticksEixo}
            allowDataOverflow
            stroke="var(--ink-muted)"
            fontSize={11}
            tickFormatter={formatarEixo}
          />
          <Tooltip
            formatter={(_valor, _nome, item) =>
              formatarValor((item.payload as PassoCascata).valor)
            }
          />
          <Bar dataKey="faixa" isAnimationActive={false}>
            <LabelList dataKey="rotuloValor" position="top" fill="var(--ink)" fontSize={11} />
            {barras.map((p, idx) => (
              <Cell key={idx} fill={corPasso(p)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', justifyContent: 'center', fontSize: '12px' }}>
        {([['Receita no período', 'data-1'], ['Receita na comparação', 'data-compare'], ['Efeito que aumenta', 'favorable'], ['Efeito que reduz', 'unfavorable']] as const).map(([texto, cor]) => (
          <span key={cor}><span aria-hidden="true" style={{ display: 'inline-block', width: 9, height: 9, marginRight: 6, background: `var(--${cor})` }} />{texto}</span>
        ))}
      </div>
    </div>
  )
}
