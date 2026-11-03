import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BarraRecorte } from '@/components/BarraRecorte'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { CartaoKpi } from '@/components/CartaoKpi'
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

export function PaginaOperacao() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { periodo, comparacao } = usePeriodo()
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

  const municipios = filtros.data?.municipios ?? []
  const alimentadores = filtros.data?.alimentadores ?? []
  const escopoAlimentador = recortes.alimentador || 'geral'
  const escopoAtipico = recortes.atipico
    ? 'com evento atípico'
    : 'sem evento atípico'

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina
        titulo="Operação"
        subtitulo={`Continuidade · ${resumoPeriodo} · ${escopoAlimentador} · ${escopoAtipico}`}
      />

      <BarraRecorte
        erro={filtros.error?.message ?? null}
        aoTentarNovamente={() => {
          void filtros.refetch()
        }}
        aoLimpar={() => {
          setSearchParams(
            limparRecortesUrl(searchParams, [
              'municipio',
              'bairro',
              'alimentador',
              'atipico',
            ]),
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
          rotulo="Alimentador"
          valor={recortes.alimentador}
          opcoes={alimentadores}
          placeholder="Geral"
          carregando={filtros.isLoading}
          aoMudar={(alimentador) => {
            setSearchParams(
              atualizarRecorteUrl(searchParams, { alimentador }),
            )
          }}
        />
        <label className="ve-switch">
          <input
            type="checkbox"
            checked={recortes.atipico}
            onChange={(e) => {
              setSearchParams(
                atualizarRecorteUrl(searchParams, {
                  atipico: e.target.checked,
                }),
              )
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
          dica="Duração Equivalente de Interrupção por Unidade Consumidora para comparar alimentadores e períodos."
          indisponivel
        />
        <CartaoKpi
          rotulo="FEC"
          unidade="vezes"
          sentidoFavoravel="baixa"
          dica="Frequência Equivalente de Interrupção por Unidade Consumidora para comparar alimentadores e períodos."
          indisponivel
        />
        <CartaoKpi
          rotulo="Eventos atípicos no período"
          sentidoFavoravel="baixa"
          indisponivel
        />
      </div>

      <Painel
        titulo="DEC e FEC por competência"
        subtitulo={`${recortes.alimentador || 'Geral'} · eixo de tempo: competência · ${escopoAtipico}`}
      >
        <EstadoIndisponivel />
      </Painel>

      <Painel
        titulo="Piores alimentadores"
        subtitulo="Ordenado por CHI (horas de consumidor interrompidas) · clique numa linha para ver a série do alimentador"
      >
        <EstadoIndisponivel />
      </Painel>
    </div>
  )
}
