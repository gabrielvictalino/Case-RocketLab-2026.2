import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Download, ListChecks } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { Abas } from '@/components/Abas'
import { BarraRecorte } from '@/components/BarraRecorte'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { Etiqueta, type VarianteEtiqueta } from '@/components/Etiqueta'
import { Painel } from '@/components/Painel'
import { Selecao } from '@/components/Selecao'
import { TabelaDados, type ColunaTabela } from '@/components/TabelaDados'
import { api, desembrulhar, type ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'
import {
  formatarDataHoraPtBr,
  formatarIntervaloPeriodo,
  formatarKwh,
  formatarNumero,
} from '@/lib/formatacao'
import {
  atualizarRecorteUrl,
  lerRecortesUrl,
  limparRecortesUrl,
} from '@/lib/recortes'
import { useFiltrosMeta } from '@/lib/useFiltrosMeta'

export type OrdemInspecao = components['schemas']['Ordem']
export type StatusOrdem = OrdemInspecao['status']
export type PaginaOrdens = components['schemas']['PaginaOrdens']

const STATUS_VALIDOS: ReadonlyArray<StatusOrdem> = [
  'ABERTA',
  'EM_CAMPO',
  'CONCLUIDA',
  'CANCELADA',
]

// eslint-disable-next-line react-refresh/only-export-components
export const ROTULO_STATUS_ORDEM: Record<StatusOrdem, string> = {
  ABERTA: 'Aberta',
  EM_CAMPO: 'Em campo',
  CONCLUIDA: 'Concluída',
  CANCELADA: 'Cancelada',
}

const VARIANTE_STATUS_ORDEM: Record<StatusOrdem, VarianteEtiqueta> = {
  ABERTA: 'atencao',
  EM_CAMPO: 'marca',
  CONCLUIDA: 'favoravel',
  CANCELADA: 'padrao',
}

const OPCOES_STATUS_ORDEM = STATUS_VALIDOS.map((status) => ({
  valor: status,
  rotulo: ROTULO_STATUS_ORDEM[status],
}))

function statusOrdemValido(valor: string | null): StatusOrdem | null {
  if (!valor) return null
  return STATUS_VALIDOS.includes(valor as StatusOrdem)
    ? (valor as StatusOrdem)
    : null
}

const TAMANHO_PAGINA = 25

export function PaginaPerdas() {
  const [searchParams, setSearchParams] = useSearchParams()
  const { periodo, carga } = usePeriodo()
  const filtros = useFiltrosMeta()
  const recortes = lerRecortesUrl(searchParams)

  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const abaUrl = searchParams.get('aba') === 'ordens' ? 'ordens' : 'fila'
  const statusFiltro = statusOrdemValido(searchParams.get('status'))
  const [pagina, setPagina] = useState(1)

  const ordensQuery = useQuery<PaginaOrdens, ErroApi>({
    queryKey: ['ordens-inspecao', statusFiltro, pagina, TAMANHO_PAGINA],
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/ordens-inspecao', {
          params: {
            query: {
              status: statusFiltro,
              page: pagina,
              size: TAMANHO_PAGINA,
            },
          },
        }),
      ),
  })

  const municipios = filtros.data?.municipios ?? []
  const bairrosPorMunicipio = filtros.data?.bairros ?? {}
  const bairrosDisponiveis = recortes.municipio
    ? (bairrosPorMunicipio[recortes.municipio] ?? [])
    : []
  const classes = filtros.data?.classes ?? []

  const selecionarAba = (novaAba: string) => {
    const proximo = new URLSearchParams(searchParams)
    if (novaAba === 'ordens') {
      proximo.set('aba', 'ordens')
    } else {
      proximo.delete('aba')
    }
    setSearchParams(proximo)
  }

  const alterarStatusOrdem = (novoStatus: string) => {
    setPagina(1)
    const proximo = new URLSearchParams(searchParams)
    if (novoStatus && statusOrdemValido(novoStatus)) {
      proximo.set('status', novoStatus)
    } else {
      proximo.delete('status')
    }
    setSearchParams(proximo)
  }

  const limparFiltroStatus = () => {
    setPagina(1)
    const proximo = new URLSearchParams(searchParams)
    proximo.delete('status')
    setSearchParams(proximo)
  }

  const colunasOrdens = useMemo<ColunaTabela<OrdemInspecao>[]>(
    () => [
      {
        accessorKey: 'id_uc',
        header: 'UC',
        cell: ({ row }) => (
          <span className="ve-mono">{row.original.id_uc}</span>
        ),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => {
          const st = row.original.status
          return (
            <Etiqueta variante={VARIANTE_STATUS_ORDEM[st]} ponto>
              {ROTULO_STATUS_ORDEM[st]}
            </Etiqueta>
          )
        },
      },
      {
        accessorKey: 'score',
        header: 'Score',
        meta: { alinhamento: 'direita' },
        cell: ({ row }) =>
          row.original.score !== null && row.original.score !== undefined
            ? formatarNumero(row.original.score, 2)
            : '—',
      },
      {
        accessorKey: 'energia_recuperar_kwh',
        header: 'Energia a recuperar',
        meta: { alinhamento: 'direita' },
        cell: ({ row }) =>
          row.original.energia_recuperar_kwh !== null &&
          row.original.energia_recuperar_kwh !== undefined
            ? formatarKwh(row.original.energia_recuperar_kwh)
            : '—',
      },
      {
        accessorKey: 'inspetor',
        header: 'Inspetor',
        cell: ({ row }) => row.original.inspetor ?? '—',
      },
      {
        accessorKey: 'atualizado_em',
        header: 'Atualizado em',
        cell: ({ row }) => formatarDataHoraPtBr(row.original.atualizado_em),
      },
    ],
    [],
  )

  const subtituloCabecalho = carga
    ? `Fila de inspeção pelo score da carga ${carga.batch_id}${rotuloPeriodo ? ` · ${rotuloPeriodo}` : ''}`
    : `Fila de inspeção e ordens de inspeção${rotuloPeriodo ? ` · ${rotuloPeriodo}` : ''}`

  const itensOrdens = ordensQuery.data?.items ?? []
  const totalOrdens = ordensQuery.data?.total
  const totalPaginas =
    totalOrdens !== undefined
      ? Math.max(1, Math.ceil(totalOrdens / TAMANHO_PAGINA))
      : 1

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina titulo="Perdas" subtitulo={subtituloCabecalho} />

      <Abas
        ariaLabel="Seções de perdas"
        abaAtiva={abaUrl}
        aoSelecionar={selecionarAba}
        abas={[
          { id: 'fila', rotulo: 'Fila' },
          {
            id: 'ordens',
            rotulo: 'Ordens',
            contador: totalOrdens ?? null,
          },
        ]}
      />

      {abaUrl === 'fila' ? (
        <>
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
                  'classe',
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
                setSearchParams(
                  atualizarRecorteUrl(searchParams, { municipio }),
                )
              }}
            />
            <Selecao
              rotulo="Bairro"
              valor={recortes.bairro}
              opcoes={bairrosDisponiveis}
              placeholder={
                recortes.municipio ? 'Todos' : 'Escolha o município'
              }
              desabilitado={!recortes.municipio}
              carregando={filtros.isLoading}
              aoMudar={(bairro) => {
                setSearchParams(atualizarRecorteUrl(searchParams, { bairro }))
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
            titulo="UCs sem ordem ativa"
            subtitulo="Ordenadas por score · energia a recuperar em kWh"
            acoes={
              <>
                <button type="button" disabled className="ve-btn">
                  <Download size={15} className="ve-icon" aria-hidden="true" />
                  <span>Exportar Excel</span>
                </button>
                <button
                  type="button"
                  disabled
                  className="ve-btn ve-btn-primary"
                >
                  <ListChecks
                    size={15}
                    className="ve-icon"
                    aria-hidden="true"
                  />
                  <span>Gerar ordens</span>
                  <span className="ve-btn-count">0</span>
                </button>
              </>
            }
          >
            <TabelaDados
              colunas={[]}
              dados={[]}
              legenda="Fila de inspeção"
              indisponivel
            />
          </Painel>
        </>
      ) : (
        <>
          <BarraRecorte aoLimpar={limparFiltroStatus}>
            <Selecao
              rotulo="Status"
              valor={statusFiltro ?? ''}
              opcoes={OPCOES_STATUS_ORDEM}
              placeholder="Todos"
              aoMudar={alterarStatusOrdem}
            />
          </BarraRecorte>

          <Painel
            titulo="Ordens de inspeção"
            subtitulo="Ciclo operacional registrado no portal"
          >
            <TabelaDados
              colunas={colunasOrdens}
              dados={itensOrdens}
              legenda="Ordens de inspeção"
              chaveLinha={(ordem) => ordem.id}
              carregando={ordensQuery.isLoading}
              erro={ordensQuery.error?.message ?? null}
              aoTentarNovamente={() => {
                void ordensQuery.refetch()
              }}
              tituloVazio="Nenhuma ordem de inspeção encontrada"
              mensagemVazio="Não há ordens de inspeção para o status selecionado."
              rodape={
                totalOrdens !== undefined ? (
                  <>
                    <span>
                      Mostrando {itensOrdens.length} de {totalOrdens} ordens de
                      inspeção
                    </span>
                    {totalPaginas > 1 && (
                      <div className="ve-row" style={{ gap: 'var(--space-2)' }}>
                        <button
                          type="button"
                          className="ve-btn ve-btn-sm"
                          disabled={pagina <= 1}
                          onClick={() => setPagina((p) => Math.max(1, p - 1))}
                        >
                          Anterior
                        </button>
                        <span>
                          Página {pagina} de {totalPaginas}
                        </span>
                        <button
                          type="button"
                          className="ve-btn ve-btn-sm"
                          disabled={pagina >= totalPaginas}
                          onClick={() =>
                            setPagina((p) => Math.min(totalPaginas, p + 1))
                          }
                        >
                          Próxima
                        </button>
                      </div>
                    )}
                  </>
                ) : undefined
              }
            />
          </Painel>
        </>
      )}
    </div>
  )
}
