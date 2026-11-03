import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BarraRecorte } from '@/components/BarraRecorte'
import { Selecao } from '@/components/Selecao'
import { Painel } from '@/components/Painel'
import { Etiqueta } from '@/components/Etiqueta'
import { TabelaDados, type ColunaTabela } from '@/components/TabelaDados'
import { api, desembrulhar, ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'
import {
  formatarDataPtBr,
  formatarKwh,
  formatarMoeda,
  formatarNumero,
} from '@/lib/formatacao'
import { mensagemErro, paginaValida, somarEnergia, TAMANHO_PAGINA } from './ordens'

type Item = components['schemas']['ItemFila']
type Pagina = components['schemas']['PaginaFila']
type Lote = components['schemas']['Lote']
type Props = {
  dados: Pagina | undefined
  atualizado: boolean
  erro: string | null
  carregando: boolean
  recortes: { municipio: string; bairro: string; classe: string }
  municipios: string[]
  bairros: string[]
  classes: string[]
  pagina: number
  mudarPagina: (pagina: number) => void
  mudarFiltro: (campo: 'municipio' | 'bairro' | 'classe', valor: string) => void
  limpar: () => void
  podeEscrever: boolean
  verOrdens: () => void
  refetch: () => void
}
export function AbaFila(props: Props) {
  const cliente = useQueryClient()
  const chave = JSON.stringify([
    props.recortes.municipio,
    props.recortes.bairro,
    props.recortes.classe,
    props.pagina,
  ])
  const [selecao, setSelecao] = useState<{ chave: string; ids: Set<string> }>({
    chave,
    ids: new Set(),
  })
  const ids = selecao.chave === chave ? selecao.ids : new Set<string>()
  const [lote, setLote] = useState<Lote | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  if (selecao.chave !== chave) {
    setSelecao({ chave, ids: new Set() })
    setErro(null)
  }
  const cabecalho = useRef<HTMLInputElement>(null)
  const itens = props.dados?.items ?? []
  useEffect(() => {
    if (cabecalho.current)
      cabecalho.current.indeterminate = ids.size > 0 && ids.size < itens.length
  }, [ids.size, itens.length])
  const { dados, pagina, mudarPagina, atualizado } = props
  useEffect(() => {
    if (!atualizado || !dados || pagina <= 1) return
    const nova = paginaValida(dados.total, dados.items.length, pagina)
    if (nova !== null && nova !== pagina) mudarPagina(nova)
  }, [dados, pagina, mudarPagina, atualizado])
  const mutacao = useMutation({
    mutationFn: (ucs: string[]) =>
      desembrulhar(api.POST('/api/v1/ordens-inspecao', { body: { ucs } })),
    onSuccess: async (resultado) => {
      setLote(resultado)
      setSelecao({ chave, ids: new Set() })
      await Promise.all([
        cliente.invalidateQueries({ queryKey: ['perdas-fila'] }),
        cliente.invalidateQueries({ queryKey: ['ordens-inspecao'] }),
      ])
    },
    onError: (erroApi: ErroApi) => {
      setErro(mensagemErro(erroApi))
      if (erroApi.status === 404 || erroApi.status === 409) {
        void cliente.invalidateQueries({
          queryKey: ['perdas-fila'],
          refetchType: 'all',
        })
        void cliente.invalidateQueries({
          queryKey: ['ordens-inspecao'],
          refetchType: 'all',
        })
      }
    },
  })
  const bloqueado = mutacao.isPending
  function selecionar(id: string, marcado: boolean) {
    const novos = new Set(ids)
    if (marcado) novos.add(id)
    else novos.delete(id)
    setSelecao({ chave, ids: novos })
  }
  const colunas: ColunaTabela<Item>[] = [
    {
      id: 'selecao',
      enableSorting: false,
      header: () => (
        <input
          ref={cabecalho}
          type="checkbox"
          aria-label="Selecionar todas as UCs da página"
          disabled={!props.podeEscrever || bloqueado}
          checked={itens.length > 0 && ids.size === itens.length}
          onChange={(evento) =>
            setSelecao({
              chave,
              ids: new Set(
                evento.target.checked ? itens.map((item) => item.id_uc) : [],
              ),
            })
          }
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          aria-label={`Selecionar ${row.original.id_uc}`}
          checked={ids.has(row.original.id_uc)}
          disabled={!props.podeEscrever || bloqueado}
          onChange={(evento) =>
            selecionar(row.original.id_uc, evento.target.checked)
          }
        />
      ),
    },
    {
      accessorKey: 'id_uc',
      header: 'UC',
      enableSorting: false,
      cell: ({ row }) => (
        <Link
          className="ve-mono"
          to={`/unidade-consumidora?uc=${encodeURIComponent(row.original.id_uc)}`}
        >
          {row.original.id_uc}
        </Link>
      ),
    },
    {
      accessorKey: 'score',
      header: 'Score',
      enableSorting: false,
      cell: ({ row }) => formatarNumero(row.original.score, 2),
    },
    { accessorKey: 'municipio', header: 'Município', enableSorting: false },
    { accessorKey: 'bairro', header: 'Bairro', enableSorting: false },
    { accessorKey: 'classe', header: 'Classe', enableSorting: false },
    {
      accessorKey: 'motivos',
      header: 'Motivo da suspeita',
      enableSorting: false,
      cell: ({ row }) => (
        <span className="ve-motivos" title={row.original.motivos.join(' · ')}>
          {row.original.motivos.join(' · ')}
        </span>
      ),
    },
    {
      accessorKey: 'energia_recuperar_kwh',
      header: 'Energia a recuperar',
      enableSorting: false,
      cell: ({ row }) => (
        <span title={formatarMoeda(row.original.energia_recuperar_reais)}>
          {formatarKwh(row.original.energia_recuperar_kwh)}
        </span>
      ),
    },
    {
      accessorKey: 'inspecao_anterior',
      header: 'Inspeção anterior',
      enableSorting: false,
      cell: ({ row }) => {
        const inspecao = row.original.inspecao_anterior
        return inspecao ? (
          <Etiqueta
            variante={
              inspecao.resultado === 'IRREGULARIDADE CONFIRMADA'
                ? 'critico'
                : 'padrao'
            }
          >
            {inspecao.resultado === 'IRREGULARIDADE CONFIRMADA'
              ? 'Irregular'
              : 'Normal'}{' '}
            · {formatarDataPtBr(inspecao.data)}
          </Etiqueta>
        ) : (
          '—'
        )
      },
    },
  ]
  const totalPaginas = Math.max(
    1,
    Math.ceil((props.dados?.total ?? 0) / TAMANHO_PAGINA),
  )
  return (
    <>
      <BarraRecorte erro={null} aoLimpar={bloqueado ? undefined : props.limpar}>
        <Selecao
          rotulo="Município"
          valor={props.recortes.municipio}
          opcoes={props.municipios}
          desabilitado={bloqueado}
          aoMudar={(valor) => props.mudarFiltro('municipio', valor)}
        />
        <Selecao
          rotulo="Bairro"
          valor={props.recortes.bairro}
          opcoes={props.bairros}
          desabilitado={bloqueado || !props.recortes.municipio}
          aoMudar={(valor) => props.mudarFiltro('bairro', valor)}
        />
        <Selecao
          rotulo="Classe"
          valor={props.recortes.classe}
          opcoes={props.classes}
          desabilitado={bloqueado}
          aoMudar={(valor) => props.mudarFiltro('classe', valor)}
        />
      </BarraRecorte>
      {!props.podeEscrever && (
        <p>
          Somente leitura: só o cargo Perdas gera e atualiza ordens de inspeção.
        </p>
      )}
      {erro && <div role="alert">{erro}</div>}
      {lote && (
        <div role="status">
          {lote.criadas.length
            ? `${lote.criadas.length} ordem(ns) gerada(s).`
            : 'Nenhuma ordem gerada.'}
          <button className="ve-btn" onClick={props.verOrdens}>
            Ver ordens abertas
          </button>
          <button
            className="ve-btn"
            aria-label="Fechar aviso"
            onClick={() => setLote(null)}
          >
            ×
          </button>
          {lote.rejeitadas.map((rejeitada) => (
            <p key={rejeitada.id_uc}>
              {rejeitada.id_uc} — {rejeitada.motivo}
            </p>
          ))}
        </div>
      )}
      <Painel
        titulo="UCs sem ordem ativa"
        subtitulo="Ordenadas por score · energia a recuperar em kWh"
        acoes={
          <>
            <button
              className="ve-btn"
              disabled
              title="Disponível na próxima leva"
            >
              Exportar Excel
            </button>
            <button
              className="ve-btn ve-btn-primary"
              disabled={!props.podeEscrever || !ids.size || bloqueado}
              onClick={() => {
                setLote(null)
                setErro(null)
                mutacao.mutate([...ids])
              }}
            >
              Gerar ordens ({ids.size})
            </button>
          </>
        }
      >
        <p className="ve-lote-resumo">
          {formatarKwh(
            somarEnergia(
              itens
                .filter((item) => ids.has(item.id_uc))
                .map((item) => item.energia_recuperar_kwh),
            ),
            2,
          )}{' '}
          a recuperar
        </p>
        <TabelaDados
          colunas={colunas}
          dados={itens}
          chaveLinha={(item) => item.id_uc}
          legenda="Fila de inspeção"
          carregando={props.carregando}
          erro={props.erro}
          aoTentarNovamente={props.refetch}
          tituloVazio="Nenhuma UC sem ordem ativa com estes filtros."
          rodape={
            props.dados && (
              <>
                <span>
                  Mostrando {itens.length} de {props.dados.total} UCs sem ordem
                  ativa ·{' '}
                  {formatarKwh(
                    props.dados.totais?.filtro?.energia_recuperar_kwh,
                  )}{' '}
                  (
                  {formatarMoeda(
                    props.dados.totais?.filtro?.energia_recuperar_reais,
                  )}
                  ) no filtro
                </span>
                {(totalPaginas > 1 || props.pagina > 1) && (
                  <div className="ve-row">
                    <button
                      className="ve-btn"
                      disabled={bloqueado || props.pagina <= 1}
                      onClick={() => props.mudarPagina(props.pagina - 1)}
                    >
                      Anterior
                    </button>
                    <span>
                      Página {props.pagina} de {totalPaginas}
                    </span>
                    <button
                      className="ve-btn"
                      disabled={bloqueado || props.pagina >= totalPaginas}
                      onClick={() => props.mudarPagina(props.pagina + 1)}
                    >
                      Próxima
                    </button>
                  </div>
                )}
              </>
            )
          }
        />
      </Painel>
    </>
  )
}
