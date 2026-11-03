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

import type { OrdenacaoOperacao } from './logicaOperacao'

export function PaginaOperacao() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { periodo, comparacao } = usePeriodo()
  const filtros = useFiltrosMeta()
  const parametroOrdenacao = searchParams.get('ordenar')
  const ordenacao: OrdenacaoOperacao = parametroOrdenacao === 'dec' || parametroOrdenacao === 'fec' ? parametroOrdenacao : 'chi'
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
          const proximos = limparRecortesUrl(searchParams, ['municipio', 'bairro', 'alimentador', 'atipico'])
          proximos.delete('ordenar')
          setSearchParams(proximos)
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
      <div role="note" className="rounded-lg border bg-muted/40 p-4 text-sm">
        Os indicadores DEC e FEC apresentados são comparativos entre períodos e alimentadores e não devem ser comparados aos limites regulatórios da ANEEL.
      </div>


      <Painel
        titulo="DEC e FEC por competência"
        subtitulo={`${recortes.alimentador || 'Geral'} · eixo de tempo: competência · ${escopoAtipico}`}
      >
        <EstadoIndisponivel />
      </Painel>

      <Painel
        titulo="Ranking de alimentadores"
        acoes={
          <label htmlFor="operacao-ordenacao" className="flex items-center gap-2 text-sm">
            Ordenar por
            <select
              id="operacao-ordenacao"
              aria-label="Ordenar por"
              className="rounded-md border bg-background px-3 py-2"
              value={ordenacao}
              onChange={(e) => {
                const proximos = new URLSearchParams(searchParams)
                proximos.set('ordenar', e.target.value)
                setSearchParams(proximos)
              }}
            >
              <option value="chi">CHI</option>
              <option value="dec">DEC</option>
              <option value="fec">FEC</option>
            </select>
          </label>
        }
        subtitulo={`Ordenado por ${ordenacao.toUpperCase()} · selecione um alimentador para acompanhar sua série de continuidade`}
      >
                <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                {['Alimentador', 'Município', 'CHI', 'DEC', 'FEC', 'UCs', 'Causa principal'].map((coluna) => (
                  <th key={coluna} scope="col" className="whitespace-nowrap px-5 py-3 font-medium">
                    {coluna}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr>
                <td colSpan={7} className="px-5 py-12 text-center">
                  <p className="font-medium">Nenhum dado disponível</p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    O ranking será exibido após a integração dos dados de continuidade.
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </Painel>
    </div>
  )
}
