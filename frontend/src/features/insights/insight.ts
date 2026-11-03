import type { Insight, ParametrosInsight, TelaInsight } from '@/features/insights/useInsight'
import type { ErroApi } from '@/lib/api/cliente'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'
import { parsePeriodo } from '@/lib/periodos'
import type { RecortesUrl } from '@/lib/recortes'

export const INSIGHT_INDISPONIVEL = 'Insight indisponível para esta combinação de períodos'
const DEMAIS_DADOS = 'Os demais dados da tela seguem válidos.'

// Os recortes que cada tela aplica aos próprios números.
const RECORTES_DA_TELA: Record<TelaInsight, ReadonlyArray<keyof ParametrosInsight>> = {
  'visao-geral': [],
  receita: ['municipio', 'bairro', 'classe'],
}

export function parametrosDoInsight(
  tela: TelaInsight,
  periodo: { periodo: string; comparacao?: string } | null,
  recortes: RecortesUrl,
): ParametrosInsight | null {
  if (!periodo) {
    return null
  }
  const parametros: ParametrosInsight = { ...periodo }
  for (const chave of RECORTES_DA_TELA[tela]) {
    const valor = recortes[chave as keyof RecortesUrl]
    if (typeof valor === 'string' && valor) {
      parametros[chave] = valor
    }
  }
  return parametros
}

// Uma resposta fora do formato (um proxy, um cache de outra versão) fica neste bloco,
// sem derrubar a tela.
export function insightValido(insight: Insight | undefined): insight is Insight {
  return (
    typeof insight?.carga?.batch_id === 'string' &&
    Array.isArray(insight.observacoes) &&
    insight.observacoes.length > 0 &&
    insight.observacoes.every(
      (observacao) =>
        typeof observacao?.texto === 'string' &&
        Array.isArray(observacao.valores) &&
        observacao.valores.every(
          (valor) => Number.isInteger(valor?.inicio) && Number.isInteger(valor?.fim),
        ),
    )
  )
}

export function rodapeDoInsight(insight: Insight): string {
  const periodo = formatarIntervaloPeriodo(parsePeriodo(insight.periodo))
  const comparacao = insight.comparacao
    ? ` × ${formatarIntervaloPeriodo(parsePeriodo(insight.comparacao))}`
    : ''
  return `Gerado para ${periodo}${comparacao} · carga ${insight.carga.batch_id}`
}

export function motivoIndisponivel(erro: ErroApi | null): string {
  // A cota é dividida com o assistente e só volta no dia seguinte: tentar de novo não adianta.
  if (erro?.code === 'COTA_DE_TOKENS_ESGOTADA') {
    return `A cota diária de IA acabou e volta à meia-noite. ${DEMAIS_DADOS}`
  }
  if (erro?.status === 429) {
    return `Muitos insights gerados agora. Tente de novo em instantes. ${DEMAIS_DADOS}`
  }
  if (erro?.code === 'COMPARACAO_INDISPONIVEL') {
    return `Escolha um período de comparação para gerar o insight. ${DEMAIS_DADOS}`
  }
  return DEMAIS_DADOS
}
