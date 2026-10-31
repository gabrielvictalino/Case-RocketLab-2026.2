import { Download } from 'lucide-react'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BlocoInsight } from '@/components/BlocoInsight'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { CartaoKpi } from '@/components/CartaoKpi'
import { EstadoIndisponivel } from '@/components/Estados'
import { Painel } from '@/components/Painel'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'

export function PaginaVisaoGeral() {
  const { periodo, comparacao, carga } = usePeriodo()

  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const rotuloComparacao = comparacao
    ? formatarIntervaloPeriodo(comparacao)
    : null

  const resumoPeriodo = rotuloPeriodo
    ? rotuloComparacao
      ? `${rotuloPeriodo} × ${rotuloComparacao}`
      : rotuloPeriodo
    : 'período atual'

  const metaInsight = carga
    ? `Gerado para ${resumoPeriodo} · carga ${carga.batch_id}`
    : `Gerado para ${resumoPeriodo}`

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina
        titulo="Visão Geral"
        subtitulo={`${resumoPeriodo} · todas as UCs · competência`}
        acoes={
          <button type="button" disabled className="ve-btn">
            <Download size={15} className="ve-icon" aria-hidden="true" />
            <span>Exportar</span>
          </button>
        }
      />

      <div className="ve-kpi-grid" aria-label="Indicadores do período">
        <CartaoKpi
          rotulo="Receita faturada"
          sentidoFavoravel="alta"
          indisponivel
        />
        <CartaoKpi
          rotulo="Receita arrecadada"
          sentidoFavoravel="alta"
          indisponivel
        />
        <CartaoKpi
          rotulo="Volume faturado"
          unidade="GWh"
          sentidoFavoravel="alta"
          indisponivel
        />
        <CartaoKpi
          rotulo="Tarifa média"
          unidade="/MWh"
          sentidoFavoravel="alta"
          indisponivel
        />
        <CartaoKpi
          rotulo="Inadimplência"
          sentidoFavoravel="baixa"
          tipoVariacao="pp"
          dica="Proporção da receita faturada ainda não arrecadada no período."
          indisponivel
        />
        <CartaoKpi
          rotulo="UCs ativas e com GD"
          pares={[
            { subrotulo: 'Ativas', sentidoFavoravel: 'alta' },
            { subrotulo: 'Com GD', sentidoFavoravel: 'alta' },
          ]}
          indisponivel
        />
        <CartaoKpi
          rotulo="Continuidade"
          dica="DEC e FEC acumulados para comparação entre períodos."
          pares={[
            { subrotulo: 'DEC (h)', sentidoFavoravel: 'baixa' },
            { subrotulo: 'FEC (vezes)', sentidoFavoravel: 'baixa' },
          ]}
          indisponivel
        />
        <CartaoKpi
          rotulo="Taxa de acerto"
          sentidoFavoravel="alta"
          tipoVariacao="pp"
          dica="Proporção de ordens de inspeção concluídas com irregularidade confirmada."
          indisponivel
        />
      </div>

      <Painel
        titulo="Receita e volume por competência"
        subtitulo="Mesmas competências nos dois gráficos · eixo de tempo: competência"
      >
        <EstadoIndisponivel />
      </Painel>

      <BlocoInsight
        titulo="Insight do período"
        meta={metaInsight}
        indisponivel
      />
    </div>
  )
}
