import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BlocoInsight } from '@/components/BlocoInsight'
import {
  INSIGHT_INDISPONIVEL,
  motivoIndisponivel,
  parametrosDoInsight,
  rodapeDoInsight,
} from '@/features/insights/insight'
import { useInsight, type TelaInsight } from '@/features/insights/useInsight'
import { lerRecortesUrl } from '@/lib/recortes'

export function InsightDaTela({ tela }: { tela: TelaInsight }) {
  const [searchParams] = useSearchParams()
  const { parametros, carregando, erro } = usePeriodo()
  const pedido = parametrosDoInsight(tela, parametros, lerRecortesUrl(searchParams))
  const insight = useInsight(tela, pedido)

  if (carregando || (!erro && insight.isPending)) {
    return <BlocoInsight carregando mensagemCarregando="Gerando insight" />
  }
  const observacoes = insight.data?.observacoes
  // Uma falha do insight fica neste bloco: o resto da tela não depende dele.
  if (erro || !insight.data || !Array.isArray(observacoes) || observacoes.length === 0) {
    return (
      <BlocoInsight
        indisponivel
        tituloIndisponivel={INSIGHT_INDISPONIVEL}
        mensagemIndisponivel={motivoIndisponivel(insight.error)}
      />
    )
  }
  return (
    <BlocoInsight
      itens={observacoes.map((observacao) => ({
        texto: observacao.texto,
        etiqueta: observacao.metrica,
        destaques: observacao.valores.map((valor) => valor.trecho),
      }))}
      rodape={rodapeDoInsight(insight.data)}
    />
  )
}
