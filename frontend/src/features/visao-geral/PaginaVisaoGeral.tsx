import { Download } from 'lucide-react'
import { useCarga } from '@/app/periodo/useCarga'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BlocoInsight } from '@/components/BlocoInsight'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { CartaoKpi } from '@/components/CartaoKpi'
import { Esqueleto, EstadoErro, EstadoVazio } from '@/components/Estados'
import { GraficoBarrasComparativas, GraficoSerieComparativa } from '@/components/Graficos'
import { Painel } from '@/components/Painel'
import {
  alinharSeries,
  montarCartoes,
  ROTULOS_INDICADORES,
  SEM_DADOS_PERIODO,
  temPontosExibiveis,
} from '@/features/visao-geral/indicadores'
import { useKpis, useSerieKpis } from '@/features/visao-geral/useKpis'
import { formatarIntervaloPeriodo, formatarMoedaCompacta, formatarNumero } from '@/lib/formatacao'
import { caminhoComPeriodo } from '@/lib/navegacao'

export function PaginaVisaoGeral() {
  const { periodo, comparacao, carga, parametros, carregando, erro } = usePeriodo()
  const cargaQuery = useCarga()
  const kpis = useKpis(parametros)
  const serie = useSerieKpis(parametros?.periodo ?? null)
  const anterior = useSerieKpis(parametros?.comparacao ?? null)
  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const rotuloComparacao = comparacao ? formatarIntervaloPeriodo(comparacao) : null
  let resumoPeriodo = rotuloPeriodo ?? 'período atual'
  if (rotuloPeriodo && rotuloComparacao) resumoPeriodo += ` × ${rotuloComparacao}`
  const metaInsight = carga
    ? `Gerado para ${resumoPeriodo} · carga ${carga.batch_id}`
    : `Gerado para ${resumoPeriodo}`
  const dados = serie.data?.serie ?? []
  const mostrarComparacao = !!parametros?.comparacao && anterior.isSuccess
  const alinhadas = alinharSeries(dados, mostrarComparacao ? anterior.data?.serie : undefined)
  const temReceita = temPontosExibiveis(alinhadas.receita)
  const temVolume = temPontosExibiveis(alinhadas.volume)
  const temDados = temReceita || temVolume
  let subtitulo = 'Mesmas competências nos dois gráficos'
  if (rotuloComparacao && mostrarComparacao) subtitulo += ` · cinza = ${rotuloComparacao}`
  if (parametros?.comparacao && anterior.isError) {
    subtitulo += ' · série de comparação indisponível'
  }

  let gradeIndicadores
  if (kpis.isError) {
    gradeIndicadores = (
      <EstadoErro
        mensagem="Não foi possível carregar os indicadores."
        aoTentarNovamente={() => { void kpis.refetch() }}
      />
    )
  } else {
    const pendente = carregando || !parametros || kpis.isPending
    gradeIndicadores = (
      <div className="ve-kpi-grid" aria-label="Indicadores do período">
        {pendente && Object.values(ROTULOS_INDICADORES).map(rotulo => (
          <CartaoKpi key={rotulo} rotulo={rotulo} carregando />
        ))}
        {!pendente && parametros && kpis.data &&
          montarCartoes(kpis.data, rotuloComparacao).map(({ id, destino, ...cartao }) => (
            <CartaoKpi
              key={id}
              {...cartao}
              destino={caminhoComPeriodo(destino, parametros)}
            />
          ))}
      </div>
    )
  }

  let conteudoSeries
  if (carregando || !parametros || serie.isPending) {
    conteudoSeries = <Esqueleto />
  } else if (serie.isError) {
    conteudoSeries = (
      <EstadoErro
        compacto
        mensagem="Não foi possível carregar a série."
        aoTentarNovamente={() => {
          void serie.refetch()
          if (parametros.comparacao) void anterior.refetch()
        }}
      />
    )
  } else if (!temDados && parametros.comparacao && anterior.isPending) {
    conteudoSeries = <Esqueleto />
  } else if (!temDados) {
    conteudoSeries = <EstadoVazio titulo={SEM_DADOS_PERIODO} mensagem="" />
  } else {
    const rotuloSerieComparacao = mostrarComparacao ? rotuloComparacao ?? undefined : undefined
    conteudoSeries = (
      <>
        {temReceita ? (
          <GraficoSerieComparativa
            dados={alinhadas.receita}
            rotuloAtual="Receita"
            rotuloComparacao={rotuloSerieComparacao}
            formatarValor={formatarMoedaCompacta}
          />
        ) : (
          <div style={{ minHeight: 220 }}>
            <EstadoVazio compacto titulo={SEM_DADOS_PERIODO} mensagem="Receita faturada" />
          </div>
        )}
        {temVolume ? (
          <GraficoBarrasComparativas
            dados={alinhadas.volume}
            rotuloAtual={`Volume (${alinhadas.unidadeVolume})`}
            rotuloComparacao={rotuloSerieComparacao}
            formatarValor={v => `${formatarNumero(v, 2)} ${alinhadas.unidadeVolume}`}
          />
        ) : (
          <div style={{ minHeight: 200 }}>
            <EstadoVazio compacto titulo={SEM_DADOS_PERIODO} mensagem="Volume faturado" />
          </div>
        )}
      </>
    )
  }

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
      {erro ? (
        <EstadoErro
          mensagem="Não foi possível carregar a carga publicada"
          aoTentarNovamente={() => { void cargaQuery.refetch() }}
        />
      ) : (
        <>
          {gradeIndicadores}
          <Painel titulo="Receita e volume por competência" subtitulo={subtitulo}>
            {conteudoSeries}
          </Painel>
        </>
      )}
      <BlocoInsight
        titulo="Insight do período"
        meta={metaInsight}
        indisponivel
        mensagemIndisponivel={
          'O insight de IA deste período será gerado na próxima versão do portal.'
        }
      />
    </div>
  )
}
