import { Download } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BarraRecorte } from '@/components/BarraRecorte'
import { BlocoInsight } from '@/components/BlocoInsight'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { EstadoIndisponivel } from '@/components/Estados'
import { Painel } from '@/components/Painel'
import { Selecao } from '@/components/Selecao'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'
import {
  atualizarRecorteUrl,
  lerRecortesUrl,
  limparRecortesUrl,
} from '@/lib/recortes'
import { useFiltrosMeta } from '@/lib/useFiltrosMeta'

export function PaginaReceita() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { periodo, comparacao, carga } = usePeriodo()
  const filtros = useFiltrosMeta()
  const recortes = lerRecortesUrl(searchParams)

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
    ? `${resumoPeriodo} · carga ${carga.batch_id}`
    : resumoPeriodo

  const municipios = filtros.data?.municipios ?? []
  const classes = filtros.data?.classes ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina
        titulo="Receita"
        subtitulo={`Receita faturada · ${resumoPeriodo}`}
        acoes={
          <button type="button" disabled className="ve-btn">
            <Download size={15} className="ve-icon" aria-hidden="true" />
            <span>Exportar</span>
          </button>
        }
      />

      <BarraRecorte
        erro={filtros.error?.message ?? null}
        aoTentarNovamente={() => {
          void filtros.refetch()
        }}
        aoLimpar={() => {
          setSearchParams(
            limparRecortesUrl(searchParams, ['municipio', 'bairro', 'classe']),
          )
        }}
      >
        <Selecao
          rotulo="Município"
          valor={recortes.municipio}
          opcoes={municipios}
          placeholder="Todos"
          carregando={filtros.isLoading}
          aoMudar={(municipio) => {
            setSearchParams(atualizarRecorteUrl(searchParams, { municipio }))
          }}
        />
        <Selecao
          rotulo="Classe"
          valor={recortes.classe}
          opcoes={classes}
          placeholder="Todos"
          carregando={filtros.isLoading}
          aoMudar={(classe) => {
            setSearchParams(atualizarRecorteUrl(searchParams, { classe }))
          }}
        />
      </BarraRecorte>

      <Painel
        titulo="De onde veio a variação"
        subtitulo="Cascata da receita: efeito-volume, reajuste, bandeira e mix · R$"
      >
        <EstadoIndisponivel />
      </Painel>

      <BlocoInsight
        titulo="Insight do período"
        meta={metaInsight}
        indisponivel
      />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.45fr) minmax(0, 1fr)',
          gap: '24px',
          alignItems: 'stretch',
        }}
      >
        <Painel
          titulo="Onde: detalhamento por local"
          subtitulo={
            recortes.municipio
              ? `${recortes.municipio} · ${recortes.classe || 'todas as classes'}`
              : `Municípios · ${recortes.classe || 'todas as classes'}`
          }
          preencher
        >
          <EstadoIndisponivel />
        </Painel>

        <Painel
          titulo="Por quê: volume por grupo de UC"
          subtitulo="Volume faturado · GWh"
          preencher
        >
          <EstadoIndisponivel />
        </Painel>
      </div>
    </div>
  )
}
