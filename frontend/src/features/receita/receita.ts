import type { components } from '@/lib/api/schema'
import type { RecortesUrl } from '@/lib/recortes'
import type { PassoCascata } from '@/components/Graficos'

type Decomposicao = components['schemas']['Decomposicao']
type Locais = components['schemas']['Locais']
type Grupos = components['schemas']['Grupos']
export const recorteReceita = (r: RecortesUrl) => ({
  municipio: r.municipio || undefined,
  classe: r.classe || undefined,
})
export const nivelLocais = (r: RecortesUrl): 'municipio' | 'bairro' =>
  r.municipio ? 'bairro' : 'municipio'
const formatadoresCompactos = new Map<number, Intl.NumberFormat>()
const formatadorIntegral = new Intl.NumberFormat('pt-BR', {
  style: 'currency', currency: 'BRL', maximumFractionDigits: 15,
})
function obterFormatadorCompacto(casas: number): Intl.NumberFormat {
  const precisao = Math.max(0, Math.min(casas, 15))
  let formatador = formatadoresCompactos.get(precisao)
  if (!formatador) {
    formatador = new Intl.NumberFormat('pt-BR', {
      style: 'currency', currency: 'BRL', notation: 'compact',
      maximumFractionDigits: precisao,
    })
    formatadoresCompactos.set(precisao, formatador)
  }
  return formatador
}
function formatadorCompacto(valor: number, casasExtras = 0) {
  const magnitude = Math.abs(valor)
  const casas = magnitude >= 1e9 ? 2 : magnitude >= 1e6 ? 0 : 1
  return obterFormatadorCompacto(casas + casasExtras)
}
export const formatarMoedaCompacta = (valor: number) =>
  formatadorCompacto(valor).format(valor)
export const formatarMoedaCompactaComSinal = (valor: number) =>
  `${valor > 0 ? '+' : valor < 0 ? '−' : ''}${formatarMoedaCompacta(Math.abs(valor))}`

// Aumenta a precisão quando o arredondamento ocultaria diferenças no gráfico.
export function formatadorCascata(valores: number[]): (valor: number) => string {
  const distintos = [...new Set(valores)]
  for (let extras = 0; extras <= 15; extras++) {
    const formatar = (valor: number) => formatadorCompacto(valor, extras).format(valor)
    if (new Set(distintos.map(formatar)).size === distintos.length) return formatar
  }
  return (valor) => formatadorIntegral.format(valor)
}
// Escolhe um passo 1/2/5 × 10ⁿ com aproximadamente cinco marcações no domínio.
export function montarEixoCascata(dominio: [number, number]) {
  const [piso, teto] = dominio
  const expoente = Math.floor(Math.log10((teto - piso) / 4))
  const candidatos = [-1, 0, 1].flatMap((deslocamento) =>
    [1, 2, 5].map((fator) => fator * 10 ** (expoente + deslocamento)),
  )
  const opcoes = candidatos.map((passo) => {
    const primeiro = Math.ceil(piso / passo)
    const ultimo = Math.floor(teto / passo)
    return { passo, primeiro, quantidade: Math.max(0, ultimo - primeiro + 1) }
  }).filter((opcao) => opcao.quantidade >= 2 && opcao.quantidade <= 8)
  opcoes.sort((a, b) => Math.abs(a.quantidade - 5) - Math.abs(b.quantidade - 5))
  const { passo, primeiro, quantidade } = opcoes[0]!
  const ticks = Array.from({ length: quantidade }, (_, i) => (primeiro + i) * passo)
  const formatar = (valor: number) => {
    const magnitude = Math.abs(valor)
    const escala = magnitude >= 1e12 ? 1e12 : magnitude >= 1e9 ? 1e9 : magnitude >= 1e6 ? 1e6 : magnitude >= 1e3 ? 1e3 : 1
    const casas = Math.max(0, Math.ceil(Math.log10(escala / passo)))
    return obterFormatadorCompacto(casas).format(valor)
  }
  return { passo, ticks, formatar }
}
export function montarPassosCascata(
  d: Decomposicao,
  rotulos: { periodo: string; comparacao: string },
): PassoCascata[] {
  return [
    {
      rotulo: 'Receita',
      detalhe: rotulos.comparacao,
      valor: Number(d.receita_base),
      tipo: 'inicio',
    },
    ...(['volume', 'reajuste', 'bandeira', 'mix'] as const).map((chave) => ({
      rotulo: {
        volume: 'Volume',
        reajuste: 'Reajuste',
        bandeira: 'Bandeira',
        mix: 'Mix',
      }[chave],
      valor: Number(d.efeitos[chave]),
      tipo: 'delta' as const,
    })),
    {
      rotulo: 'Receita',
      detalhe: rotulos.periodo,
      valor: Number(d.receita_atual),
      tipo: 'fim',
    },
  ]
}
export function montarLinhasLocais(l: Locais, nivel: 'municipio' | 'bairro') {
  const total = Number(l.total.variacao)
  return l.itens.map((item) => ({
    chave: `${item.municipio}|${item.bairro ?? ''}`,
    municipio: item.municipio,
    rotulo:
      nivel === 'bairro' ? (item.bairro ?? 'Bairro não informado') : item.municipio,
    atual: Number(item.receita_atual),
    base: Number(item.receita_base),
    variacao: item.variacao_pct === null ? null : Number(item.variacao_pct) / 100,
    volume: Number(item.efeitos.volume),
    parte: total === 0 ? null : Number(item.variacao) / total,
  }))
}
export function montarLinhasGrupos(g: Grupos) {
  const ordem = ['GD', 'IRREGULARIDADE_CONFIRMADA', 'DEMAIS'] as const
  const rotulos = {
    GD: 'Com GD',
    IRREGULARIDADE_CONFIRMADA: 'Com irregularidade confirmada',
    DEMAIS: 'Demais',
  }
  return ordem.flatMap((grupo) =>
    g.itens
      .filter((i) => i.grupo_uc === grupo)
      .map((i) => ({
        rotulo: rotulos[grupo],
        atual: Number(i.volume_atual_kwh) / 1e6,
        base: Number(i.volume_base_kwh) / 1e6,
        variacao:
          i.variacao_volume_pct === null ? null : Number(i.variacao_volume_pct) / 100,
      })),
  )
}
