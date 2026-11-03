import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BlocoInsight } from '@/components/BlocoInsight'
import {
  INSIGHT_INDISPONIVEL,
  insightValido,
  motivoIndisponivel,
  parametrosDoInsight,
  rodapeDoInsight,
} from '@/features/insights/insight'
import { useInsight, type TelaInsight } from '@/features/insights/useInsight'
import { lerRecortesUrl } from '@/lib/recortes'

export function InsightDaTela({ tela }: { tela: TelaInsight }) {
  const [searchParams] = useSearchParams()
  const { carga, parametros, carregando, erro } = usePeriodo()
  const pedido = parametrosDoInsight(tela, parametros, lerRecortesUrl(searchParams))
  const insight = useInsight(tela, pedido, carga?.id ?? null)

  if (carregando || (!erro && insight.isPending)) {
    return <BlocoInsight carregando mensagemCarregando="Gerando insight" />
  }
  // Uma falha do insight fica neste bloco: o resto da tela não depende dele.
  if (erro || !insightValido(insight.data)) {
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
      itens={insight.data.observacoes.map((observacao) => ({
        texto: observacao.texto,
        etiqueta: observacao.metrica,
        // A posição que o backend conferiu, e não uma busca pelo trecho no texto.
        destaques: observacao.valores.map(({ inicio, fim }) => ({ inicio, fim })),
      }))}
      rodape={rodapeDoInsight(insight.data)}
    />
  )
}
