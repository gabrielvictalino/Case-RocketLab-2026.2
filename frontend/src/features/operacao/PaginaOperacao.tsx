import { useState } from 'react'
import { useSearchParams } from 'react-router'
import { useCarga } from '@/app/periodo/useCarga'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BarraRecorte } from '@/components/BarraRecorte'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { CartaoKpi } from '@/components/CartaoKpi'
import { Esqueleto, EstadoIndisponivel } from '@/components/Estados'
import { GraficoSerieComparativa } from '@/components/Graficos'
import { Painel } from '@/components/Painel'
import { Selecao } from '@/components/Selecao'
import { TabelaDados, type ColunaTabela } from '@/components/TabelaDados'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'
import { atualizarRecorteUrl, lerRecortesUrl, limparRecortesUrl } from '@/lib/recortes'
import { useFiltrosMeta } from '@/lib/useFiltrosMeta'
import {
  formatarContinuidade,
  montarSerieContinuidade,
  numeroContinuidade,
  variacaoContinuidade,
} from './apresentacaoOperacao'
import {
  useRankingContinuidade,
  useSerieContinuidade,
  type AlimentadorContinuidade,
  type OrdemContinuidade,
} from './useOperacao'

const colunasRanking: ColunaTabela<AlimentadorContinuidade, unknown>[] = [
  { accessorKey: 'alimentador', header: 'Alimentador' },
  { accessorKey: 'municipio', header: 'Município' },
  {
    id: 'chi',
    header: 'CHI',
    accessorFn: (linha) => numeroContinuidade(linha.chi),
    cell: ({ row }) => formatarContinuidade(row.original.chi),
  },
  {
    id: 'dec',
    header: 'DEC (h)',
    accessorFn: (linha) => numeroContinuidade(linha.dec),
    cell: ({ row }) => formatarContinuidade(row.original.dec),
  },
  {
    id: 'fec',
    header: 'FEC (vezes)',
    accessorFn: (linha) => numeroContinuidade(linha.fec),
    cell: ({ row }) => formatarContinuidade(row.original.fec),
  },
  {
    id: 'numero_ucs',
    header: 'Nº de UCs',
    accessorFn: (linha) => linha.numero_ucs,
    cell: ({ row }) => formatarContinuidade(row.original.numero_ucs, 0),
  },
  {
    id: 'causa',
    header: 'Causa mais frequente',
    accessorFn: (linha) => linha.causas[0]?.causa ?? '—',
  },
]

export function PaginaOperacao() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [revisaoOrdenacao, setRevisaoOrdenacao] = useState(0)
  const { periodo, comparacao, parametros, carga, carregando, erro } = usePeriodo()
  const cargaQuery = useCarga()
  const filtrosMeta = useFiltrosMeta()
  const recortes = lerRecortesUrl(searchParams)

  const parametroOrdem = searchParams.get('ordem')
  const ordem: OrdemContinuidade =
    parametroOrdem === 'dec' || parametroOrdem === 'fec' ? parametroOrdem : 'chi'

  const filtros = {
    municipio: recortes.municipio,
    alimentador: recortes.alimentador,
    comEventoAtipico: searchParams.get('atipico') !== '0',
  }

  const serie = useSerieContinuidade(parametros, filtros, carga?.batch_id)
  const ranking = useRankingContinuidade(parametros, { ...filtros, alimentador: undefined }, ordem, carga?.batch_id)

  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const rotuloComparacao = comparacao ? formatarIntervaloPeriodo(comparacao) : null
  const resumoPeriodo = rotuloPeriodo
    ? rotuloComparacao
      ? `${rotuloPeriodo} × ${rotuloComparacao}`
      : rotuloPeriodo
    : 'período atual'

  const escopoAtipico = filtros.comEventoAtipico
    ? 'com evento atípico'
    : 'sem evento atípico'

  const totais = serie.data?.totais
  const totaisComparacao = serie.data?.dados_comparacao?.totais

  const dadosDec = montarSerieContinuidade(serie.data, 'dec')
  const dadosFec = montarSerieContinuidade(serie.data, 'fec')

  function selecionarAlimentador(alimentador: string) {
    setSearchParams(atualizarRecorteUrl(searchParams, { alimentador }))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina
        titulo="Operação"
        subtitulo={`Continuidade · ${resumoPeriodo} · ${recortes.alimentador || 'geral'} · ${escopoAtipico}`}
      />

      <BarraRecorte
        erro={filtrosMeta.error?.message ?? null}
        aoTentarNovamente={() => { void filtrosMeta.refetch() }}
        aoLimpar={() => {
          const proximos = limparRecortesUrl(
            searchParams,
            ['municipio', 'bairro', 'alimentador', 'atipico'],
          )
          proximos.delete('ordem')
          proximos.delete('ordenar')
          setRevisaoOrdenacao((atual) => atual + 1)
          setSearchParams(proximos)
        }}
      >
        <Selecao
          rotulo="Município"
          valor={recortes.municipio}
          opcoes={filtrosMeta.data?.municipios ?? []}
          placeholder="Todos"
          carregando={filtrosMeta.isLoading}
          aoMudar={(municipio) => {
            setSearchParams(atualizarRecorteUrl(searchParams, { municipio }))
          }}
        />
        <Selecao
          rotulo="Alimentador"
          valor={recortes.alimentador}
          opcoes={filtrosMeta.data?.alimentadores ?? []}
          placeholder="Geral"
          carregando={filtrosMeta.isLoading}
          aoMudar={selecionarAlimentador}
        />
        <label className="ve-switch">
          <input
            type="checkbox"
            checked={filtros.comEventoAtipico}
            onChange={(evento) => {
              const proximos = new URLSearchParams(searchParams)
              if (evento.target.checked) {
                proximos.delete('atipico')
              } else {
                proximos.set('atipico', '0')
              }
              setSearchParams(proximos)
            }}
          />
          <span className="ve-switch-track" aria-hidden="true" />
          <span className="ve-switch-text">
            Com evento atípico
            <small>Vale para a série e o ranking</small>
          </span>
        </label>
      </BarraRecorte>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, minmax(0, 1fr))',
          gap: '16px',
        }}
        aria-label="Indicadores de continuidade"
      >
        <CartaoKpi
          rotulo="DEC"
          unidade="h"
          sentidoFavoravel="baixa"
          dica="Duração Equivalente de Interrupção por Unidade Consumidora."
          carregando={!erro && (carregando || serie.isPending)}
          indisponivel={Boolean(erro || serie.isError)}
          mensagemIndisponivel={erro ? 'Não foi possível carregar o período.' : 'Não foi possível carregar os indicadores.'}
          semDados={serie.isSuccess && numeroContinuidade(totais?.dec) === null}
          valor={formatarContinuidade(totais?.dec)}
          variacao={variacaoContinuidade(totais?.dec, totaisComparacao?.dec)}
          valorComparado={totaisComparacao
            ? `${formatarContinuidade(totaisComparacao.dec)} h`
            : undefined}
          rotuloComparacao={rotuloComparacao ?? undefined}
          semPeriodoComparacao={!comparacao}
        />
        <CartaoKpi
          rotulo="FEC"
          unidade="vezes"
          sentidoFavoravel="baixa"
          dica="Frequência Equivalente de Interrupção por Unidade Consumidora."
          carregando={!erro && (carregando || serie.isPending)}
          indisponivel={Boolean(erro || serie.isError)}
          mensagemIndisponivel={erro ? 'Não foi possível carregar o período.' : 'Não foi possível carregar os indicadores.'}
          semDados={serie.isSuccess && numeroContinuidade(totais?.fec) === null}
          valor={formatarContinuidade(totais?.fec)}
          variacao={variacaoContinuidade(totais?.fec, totaisComparacao?.fec)}
          valorComparado={totaisComparacao
            ? `${formatarContinuidade(totaisComparacao.fec)} vezes`
            : undefined}
          rotuloComparacao={rotuloComparacao ?? undefined}
          semPeriodoComparacao={!comparacao}
        />
        <CartaoKpi
          rotulo="Eventos atípicos no período"
          sentidoFavoravel="baixa"
          indisponivel
          mensagemIndisponivel="Contagem não disponibilizada pela API de continuidade."
        />
      </div>

      {(erro || serie.isError) && (
        <div role="alert" className="rounded-lg border p-4 text-sm">
          Não foi possível carregar os indicadores de continuidade.
          <button
            type="button"
            className="ml-3 underline"
            onClick={() => { void (erro ? cargaQuery.refetch() : serie.refetch()) }}
          >
            Tentar novamente
          </button>
        </div>
      )}

      <div role="note" className="rounded-lg border bg-muted/40 p-4 text-sm">
        Os indicadores DEC e FEC apresentados são comparativos entre períodos e
        alimentadores e não devem ser comparados aos limites regulatórios da ANEEL.
      </div>

      <Painel
        titulo="DEC e FEC por competência"
        subtitulo={`${recortes.alimentador || 'Geral'} · eixo de tempo: competência · ${escopoAtipico}`}
      >
        {erro || serie.isError ? (
          <EstadoIndisponivel />
        ) : carregando || serie.isPending ? (
          <div role="status" aria-label="Carregando gráficos de continuidade" className="p-4">
            <Esqueleto linhas={6} altura={18} />
          </div>
        ) : (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 320px), 1fr))',
              gap: '24px',
            }}
          >
            <div>
              <h3 className="mb-3 font-medium">DEC (h)</h3>
              <GraficoSerieComparativa
                dados={dadosDec}
                rotuloAtual={rotuloPeriodo ?? 'Período atual'}
                rotuloComparacao={rotuloComparacao ?? undefined}
                indisponivel={serie.isSuccess && !dadosDec.some((ponto) => ponto.atual !== null || ponto.comparacao !== null)}
              />
            </div>
            <div>
              <h3 className="mb-3 font-medium">FEC (vezes)</h3>
              <GraficoSerieComparativa
                dados={dadosFec}
                rotuloAtual={rotuloPeriodo ?? 'Período atual'}
                rotuloComparacao={rotuloComparacao ?? undefined}
                indisponivel={serie.isSuccess && !dadosFec.some((ponto) => ponto.atual !== null || ponto.comparacao !== null)}
              />
            </div>
          </div>
        )}
      </Painel>

      <Painel
        titulo="Ranking de alimentadores"
        subtitulo={`Ordenado por ${ordem.toUpperCase()} · clique em uma linha para acompanhar a série do alimentador`}
        acoes={
          <label htmlFor="operacao-ordenacao" className="flex items-center gap-2 text-sm">
            Ordenar por
            <select
              id="operacao-ordenacao"
              aria-label="Ordenar por"
              className="rounded-md border bg-background px-3 py-2"
              value={ordem}
              onChange={(evento) => {
                const proximos = new URLSearchParams(searchParams)
                proximos.set('ordem', evento.target.value)
                proximos.delete('ordenar')
                setRevisaoOrdenacao((atual) => atual + 1)
                setSearchParams(proximos)
              }}
            >
              <option value="chi">CHI</option>
              <option value="dec">DEC</option>
              <option value="fec">FEC</option>
            </select>
          </label>
        }
      >
        <TabelaDados
          key={`${ordem}-${revisaoOrdenacao}`}
          legenda="Ranking de alimentadores"
          colunas={colunasRanking}
          dados={ranking.data?.ranking ?? []}
          chaveLinha={(linha) => linha.alimentador}
          aoClicarLinha={(linha) => selecionarAlimentador(linha.alimentador)}
          carregando={!erro && (carregando || ranking.isPending)}
          erro={erro ? 'Não foi possível carregar o período.' : ranking.isError ? 'Não foi possível carregar o ranking.' : null}
          aoTentarNovamente={() => { void (erro ? cargaQuery.refetch() : ranking.refetch()) }}
          tituloVazio="Nenhum dado disponível"
          mensagemVazio="Não há alimentadores para os filtros selecionados."
        />
      </Painel>
    </div>
  )
}
