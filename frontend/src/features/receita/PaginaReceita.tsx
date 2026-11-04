import { Download } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { BarraRecorte } from '@/components/BarraRecorte'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import {
  Esqueleto,
  EstadoErro,
  EstadoIndisponivel,
  EstadoVazio,
} from '@/components/Estados'
import { GraficoCascata, montarBarrasCascata } from '@/components/Graficos'
import { TabelaDados, type ColunaTabela } from '@/components/TabelaDados'
import { QUERY_KEY_CARGA } from '@/app/periodo/useCarga'
import { ErroApi } from '@/lib/api/cliente'
import {
  formatarIntervaloPeriodo,
  formatarMoeda,
  formatarNumero,
  formatarVariacao,
  formatarPercentual,
} from '@/lib/formatacao'
import {
  formatarMoedaCompacta,
  formatarMoedaCompactaComSinal,
  formatadorCascata,
  montarEixoCascata,
  montarLinhasGrupos,
  montarLinhasLocais,
  montarPassosCascata,
  nivelLocais,
  recorteReceita,
} from './receita'
import { useDecomposicao, useGrupos, useLocais } from './useReceita'
import { Painel } from '@/components/Painel'
import { Selecao } from '@/components/Selecao'
import { InsightDaTela } from '@/features/insights/InsightDaTela'
import { atualizarRecorteUrl, lerRecortesUrl, limparRecortesUrl } from '@/lib/recortes'
import { useFiltrosMeta } from '@/lib/useFiltrosMeta'

export function PaginaReceita() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { periodo, comparacao, carga, parametros, carregando, erro } = usePeriodo()
  const queryClient = useQueryClient()
  const filtros = useFiltrosMeta()
  const recortes = lerRecortesUrl(searchParams)

  const recorte = recorteReceita(recortes)
  const nivel = nivelLocais(recortes)
  const decomposicao = useDecomposicao(parametros, recorte, carga?.batch_id)
  const locais = useLocais(parametros, recorte, nivel, carga?.batch_id)
  const grupos = useGrupos(parametros, recorte, carga?.batch_id)
  const estado = (consulta: {
    isPending: boolean
    error: unknown
    refetch: () => unknown
  }) => {
    if (carregando) return <Esqueleto />
    if (erro)
      return (
        <EstadoErro
          mensagem={erro.message}
          aoTentarNovamente={() => {
            void queryClient.refetchQueries({ queryKey: QUERY_KEY_CARGA })
          }}
        />
      )
    if (!comparacao)
      return (
        <EstadoIndisponivel mensagem="Sem período de comparação disponível para decompor a variação." />
      )
    if (consulta.isPending) return <Esqueleto />
    if (
      consulta.error instanceof ErroApi &&
      consulta.error.code === 'COMPARACAO_INDISPONIVEL'
    )
      return (
        <EstadoIndisponivel mensagem="Sem período de comparação disponível para decompor a variação." />
      )
    if (consulta.error)
      return (
        <EstadoErro
          mensagem={
            consulta.error instanceof Error
              ? consulta.error.message
              : 'Erro ao carregar dados'
          }
          aoTentarNovamente={() => {
            void consulta.refetch()
          }}
        />
      )
    return null
  }
  const linhasLocais = locais.data ? montarLinhasLocais(locais.data, nivel) : []
  const linhasGrupos = grupos.data ? montarLinhasGrupos(grupos.data) : []
  const maxReceita = Math.max(0, ...linhasLocais.map((linha) => linha.atual))
  const totalVariacao = locais.data ? Number(locais.data.total.variacao) : 0
  const badge = (valor: number | null) => (
    <span className={`ve-badge ${valor === null || valor === 0 ? '' : valor > 0 ? 've-badge-favorable' : 've-badge-unfavorable'}`}>
      {formatarVariacao(valor)}
    </span>
  )
  type LinhaLocal = (typeof linhasLocais)[number]
  type LinhaGrupo = (typeof linhasGrupos)[number]
  const colunasLocais: ColunaTabela<LinhaLocal, unknown>[] = [
    {
      accessorKey: 'rotulo',
      header: nivel === 'municipio' ? 'Município' : 'Bairro',
      cell: ({ row }) =>
        nivel === 'municipio' ? (
          <button
            type="button"
            style={{ border: 0, padding: 0, background: 'none', color: 'var(--brand)', cursor: 'pointer', textDecoration: 'underline' }}
            aria-label={`Ver bairros de ${row.original.municipio}`}
            onClick={() =>
              setSearchParams(
                atualizarRecorteUrl(searchParams, {
                  municipio: row.original.municipio,
                }),
              )
            }
          >
            {row.original.rotulo}
          </button>
        ) : (
          row.original.rotulo
        ),
    },
    {
      accessorKey: 'atual',
      header: 'Período',
      cell: ({ row }) => (
        <div>
          {formatarMoedaCompacta(row.original.atual)}
          {maxReceita > 0 && row.original.atual > 0 && <div aria-hidden="true" style={{ height: 3, width: `${row.original.atual / maxReceita * 100}%`, background: 'var(--data-1)' }} />}
        </div>
      ),
    },
    {
      accessorKey: 'base',
      header: 'Comparação',
      cell: ({ row }) => formatarMoedaCompacta(row.original.base),
    },
    {
      accessorKey: 'variacao',
      header: 'Variação',
      cell: ({ row }) => badge(row.original.variacao),
    },
    {
      accessorKey: 'volume',
      header: 'Efeito-volume',
      cell: ({ row }) => formatarMoedaCompacta(row.original.volume),
    },
    {
      accessorKey: 'parte',
      header: totalVariacao > 0 ? 'Da alta total' : totalVariacao < 0 ? 'Da queda total' : 'Da variação total',
      cell: ({ row }) => formatarPercentual(row.original.parte),
    },
  ]
  const colunasGrupos: ColunaTabela<LinhaGrupo, unknown>[] = [
    { accessorKey: 'rotulo', header: 'Grupo', enableSorting: false },
    {
      accessorKey: 'atual',
      header: 'Período',
      cell: ({ row }) => formatarNumero(row.original.atual),
    },
    {
      accessorKey: 'base',
      header: 'Comparação',
      cell: ({ row }) => formatarNumero(row.original.base),
    },
    {
      accessorKey: 'variacao',
      header: 'Variação',
      cell: ({ row }) => badge(row.original.variacao),
    },
  ]
  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const rotuloComparacao = comparacao ? formatarIntervaloPeriodo(comparacao) : null

  const resumoPeriodo = rotuloPeriodo
    ? rotuloComparacao
      ? `${rotuloPeriodo} × ${rotuloComparacao}`
      : rotuloPeriodo
    : 'período atual'

  const dadosCascata = decomposicao.data
  const temReceita =
    dadosCascata &&
    (Number(dadosCascata.receita_base) !== 0 ||
      Number(dadosCascata.receita_atual) !== 0)
  const estadoCascata = estado(decomposicao)
  let conteudoCascata = estadoCascata
  if (!conteudoCascata && temReceita) {
    const passos = montarPassosCascata(dadosCascata, {
      periodo: rotuloPeriodo ?? '', comparacao: rotuloComparacao ?? '',
    })
    const { dominio, eixoTruncado } = montarBarrasCascata(passos)
    const { ticks, formatar: formatarEixo } = montarEixoCascata(dominio)
    const formatarTotais = formatadorCascata([passos[0]!.valor, passos[passos.length - 1]!.valor])
    conteudoCascata = (
      <>
      <GraficoCascata
        passos={passos}
        formatarValor={formatarMoeda}
        formatarEixo={formatarEixo}
        ticksEixo={ticks}
        formatarRotulo={(valor, tipo) => tipo === 'delta' ? formatarMoedaCompactaComSinal(valor) : formatarTotais(valor)}
      />
      {eixoTruncado && <p>O eixo não começa em zero para tornar os efeitos legíveis.</p>}
      </>
    )
  }
  if (!conteudoCascata) {
    conteudoCascata = <EstadoVazio titulo="Sem receita faturada no recorte" />
  }

  const rotuloClasse = recortes.classe
    ? `classe ${recortes.classe}`
    : 'todas as classes'
  const rotuloLocal = recortes.municipio
    ? `Bairros de ${recortes.municipio}`
    : 'Municípios'
  let subtituloReceita = `Receita faturada · ${resumoPeriodo}`
  if (dadosCascata) {
    const variacao = Number(dadosCascata.variacao)
    const percentual =
      dadosCascata.variacao_pct === null
        ? null
        : Number(dadosCascata.variacao_pct) / 100
    subtituloReceita += ` · ${formatarMoedaCompactaComSinal(variacao)}${percentual === null ? '' : ` (${formatarVariacao(percentual).replace('-', '−')})`}`
  }

  const classes = filtros.data?.classes ?? []

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina
        titulo="Receita"
        subtitulo={subtituloReceita}
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
        subtitulo={`Cascata da receita · ${recortes.municipio || 'todos os municípios'} · ${rotuloClasse} · R$`}
      >
        {conteudoCascata}
      </Painel>

      <InsightDaTela tela="receita" />

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.6fr) minmax(0, 1fr)',
          gap: '24px',
          alignItems: 'stretch',
        }}
      >
        <Painel
          titulo="Onde: detalhamento por local"
          subtitulo={`${rotuloLocal} · ${recortes.municipio || 'todos os municípios'} · ${rotuloClasse} · Receita: ${resumoPeriodo}`}
          className="ve-receita-tabela"
          preencher
        >
          <nav aria-label="Detalhamento por local">
          {nivel === 'bairro' ? (
            <p>
              <button
                type="button"
                style={{ border: 0, padding: 0, background: 'none', color: 'var(--brand)', cursor: 'pointer', textDecoration: 'underline' }}
                onClick={() =>
                  setSearchParams(atualizarRecorteUrl(searchParams, { municipio: '' }))
                }
              >
                Todos os municípios
              </button>{' '}
              › {recortes.municipio}
            </p>
          ) : (
            <p>
              Todos os municípios · clique num município para ver os bairros
            </p>
          )}
          </nav>
          {estado(locais) ?? (
            <TabelaDados
              colunas={colunasLocais}
              dados={linhasLocais}
              legenda="Detalhamento por local"
              chaveLinha={(linha) => linha.chave}
              ordenacaoInicial={[{ id: 'atual', desc: true }]}
            />
          )}
        </Painel>

        <Painel
          titulo="Por quê: volume por grupo de UC"
          subtitulo={`Volume faturado · GWh · ${recortes.municipio || 'todos os municípios'} · ${rotuloClasse} · ${resumoPeriodo}`}
          className="ve-receita-tabela"
          preencher
        >
          <p>
            Grupo de UC na competência: com GD a partir da conexão; irregularidade
            confirmada a partir da primeira inspeção que a confirmou; demais UCs.
          </p>
          {estado(grupos) ?? (
            <TabelaDados
              colunas={colunasGrupos}
              dados={linhasGrupos}
              legenda="Volume por grupo de UC"
            />
          )}
        </Painel>
      </div>
    </div>
  )
}
