import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { BarraRecorte } from '@/components/BarraRecorte'
import { Selecao } from '@/components/Selecao'
import { Painel } from '@/components/Painel'
import { Etiqueta, type VarianteEtiqueta } from '@/components/Etiqueta'
import { TabelaDados, type ColunaTabela } from '@/components/TabelaDados'
import { api, desembrulhar, ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'
import {
  formatarDataHoraPtBr,
  formatarKwh,
  formatarMoeda,
  formatarNumero,
} from '@/lib/formatacao'
import {
  acoesDisponiveis,
  invalidaKpis,
  paginaValida,
  montarPayload,
  mensagemErro,
  ROTULOS,
  TAMANHO_PAGINA,
  type AcaoOrdem,
  type Valores,
} from './ordens'
import { FormularioAcaoOrdem } from './FormularioAcaoOrdem'
import { rotulosOrdem } from './rotulosOrdem'

type Ordem = components['schemas']['Ordem']
type Status = Ordem['status']
type Pagina = components['schemas']['PaginaOrdens']
const variantes: Record<Status, VarianteEtiqueta> = {
  ABERTA: 'atencao',
  EM_CAMPO: 'marca',
  CONCLUIDA: 'favoravel',
  CANCELADA: 'padrao',
}
type Props = {
  dados: Pagina | undefined
  atualizado: boolean
  carregando: boolean
  erro: string | null
  status: Status | null
  mudarStatus: (status: string) => void
  pagina: number
  mudarPagina: (pagina: number) => void
  podeEscrever: boolean
  refetch: () => void
}
export function AbaOrdens(props: Props) {
  const focoAoFechar = useCallback(
    () => document.getElementById('titulo-ordens'),
    [],
  )
  const cliente = useQueryClient()
  const [acao, setAcao] = useState<{ ordem: Ordem; acao: AcaoOrdem } | null>(
    null,
  )
  const [erro, setErro] = useState<string | null>(null)
  const { dados, pagina, mudarPagina, atualizado } = props
  useEffect(() => {
    if (!atualizado || !dados || pagina <= 1) return
    const nova = paginaValida(dados.total, dados.items.length, pagina)
    if (nova !== null && nova !== pagina) mudarPagina(nova)
  }, [dados, pagina, mudarPagina, atualizado])
  const invalidar = () =>
    Promise.all([
      cliente.invalidateQueries({
        queryKey: ['perdas-fila'],
        refetchType: 'all',
      }),
      cliente.invalidateQueries({
        queryKey: ['ordens-inspecao'],
        refetchType: 'all',
      }),
    ])
  const mutacao = useMutation({
    mutationFn: ({
      acaoSelecionada,
      valores,
    }: {
      acaoSelecionada: NonNullable<typeof acao>
      valores: Valores
    }) => {
      const params = { path: { id_: acaoSelecionada.ordem.id } }
      if (acaoSelecionada.acao === 'despachar')
        return desembrulhar(
          api.POST('/api/v1/ordens-inspecao/{id_}/despachar', {
            params,
            body: montarPayload(
              acaoSelecionada.acao,
              valores,
            ) as components['schemas']['Despacho'],
          }),
        )
      if (acaoSelecionada.acao === 'tentativas')
        return desembrulhar(
          api.POST('/api/v1/ordens-inspecao/{id_}/tentativas', {
            params,
            body: montarPayload(
              acaoSelecionada.acao,
              valores,
            ) as components['schemas']['Tentativa'],
          }),
        )
      if (acaoSelecionada.acao === 'resultado')
        return desembrulhar(
          api.POST('/api/v1/ordens-inspecao/{id_}/resultado', {
            params,
            body: montarPayload(
              acaoSelecionada.acao,
              valores,
            ) as components['schemas']['Resultado'],
          }),
        )
      return desembrulhar(
        api.POST('/api/v1/ordens-inspecao/{id_}/cancelar', {
          params,
          body: montarPayload(
            acaoSelecionada.acao,
            valores,
          ) as components['schemas']['Cancelamento'],
        }),
      )
    },
    onSuccess: async (_resultado, variaveis) => {
      setAcao(null)
      setErro(null)
      await Promise.all([
        invalidar(),
        ...(invalidaKpis(variaveis.acaoSelecionada.acao)
          ? [cliente.invalidateQueries({ queryKey: ['kpis'] })]
          : []),
      ])
    },
    onError: (erroApi: ErroApi) => {
      setErro(mensagemErro(erroApi))
      if (erroApi.status === 404 || erroApi.status === 409) void invalidar()
    },
  })
  const colunas: ColunaTabela<Ordem>[] = [
    {
      accessorKey: 'id_uc',
      header: 'UC',
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
      accessorKey: 'status',
      header: 'Status',
      cell: ({ row }) => (
        <>
          <Etiqueta variante={variantes[row.original.status]} ponto>
            {rotulosOrdem[row.original.status]}
          </Etiqueta>
          {row.original.status === 'CONCLUIDA' && (
            <div>
              {row.original.resultado} ·{' '}
              {row.original.tipo_irregularidade ?? '—'} ·{' '}
              {formatarKwh(row.original.kwh_recuperado)}
            </div>
          )}
          {row.original.status === 'CANCELADA' && (
            <div>{row.original.motivo_cancelamento}</div>
          )}
        </>
      ),
    },
    {
      accessorKey: 'score',
      header: 'Score',
      cell: ({ row }) => formatarNumero(row.original.score, 2),
    },
    {
      accessorKey: 'motivos',
      header: 'Motivo da suspeita',
      cell: ({ row }) => (
        <span className="ve-motivos" title={row.original.motivos.join(' · ')}>
          {row.original.motivos.join(' · ')}
        </span>
      ),
    },
    {
      accessorKey: 'energia_recuperar_kwh',
      header: 'Energia a recuperar',
      cell: ({ row }) => (
        <span title={formatarMoeda(row.original.energia_recuperar_reais)}>
          {formatarKwh(row.original.energia_recuperar_kwh)}
        </span>
      ),
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
    {
      id: 'acoes',
      header: 'Ações',
      enableSorting: false,
      cell: ({ row }) => (
        <div className="ve-acoes-ordem">
          {acoesDisponiveis(row.original.status).map((acaoDisponivel) => (
            <button
              type="button"
              className="ve-btn ve-btn-sm"
              disabled={!props.podeEscrever}
              key={acaoDisponivel}
              onClick={() => {
                setErro(null)
                setAcao({ ordem: row.original, acao: acaoDisponivel })
              }}
            >
              {ROTULOS[acaoDisponivel]}
            </button>
          ))}
        </div>
      ),
    },
  ]
  const paginas = Math.max(
    1,
    Math.ceil((props.dados?.total ?? 0) / TAMANHO_PAGINA),
  )
  const itens = props.dados?.items ?? []
  return (
    <>
      <BarraRecorte aoLimpar={() => props.mudarStatus('')}>
        <Selecao
          rotulo="Status"
          valor={props.status ?? ''}
          opcoes={Object.entries(rotulosOrdem).map(([valor, rotulo]) => ({
            valor,
            rotulo,
          }))}
          aoMudar={props.mudarStatus}
        />
      </BarraRecorte>
      {!props.podeEscrever && (
        <p>
          Somente leitura: só o cargo Perdas gera e atualiza ordens de inspeção.
        </p>
      )}
      <Painel
        titulo={
          <span id="titulo-ordens" tabIndex={-1}>
            Ordens de inspeção
          </span>
        }
        subtitulo="Ciclo operacional registrado no portal"
      >
        <TabelaDados
          colunas={colunas}
          dados={itens}
          legenda="Ordens de inspeção"
          chaveLinha={(ordem) => ordem.id}
          carregando={props.carregando}
          erro={props.erro}
          aoTentarNovamente={props.refetch}
          tituloVazio="Nenhuma ordem de inspeção encontrada"
          mensagemVazio="Não há ordens de inspeção para o status selecionado."
          rodape={
            props.dados && (
              <>
                <span>
                  Mostrando {itens.length} de {props.dados.total} ordens de
                  inspeção
                </span>
                {(paginas > 1 || props.pagina > 1) && (
                  <div className="ve-row">
                    <button
                      className="ve-btn"
                      disabled={props.pagina <= 1}
                      onClick={() => props.mudarPagina(props.pagina - 1)}
                    >
                      Anterior
                    </button>
                    <span>
                      Página {props.pagina} de {paginas}
                    </span>
                    <button
                      className="ve-btn"
                      disabled={props.pagina >= paginas}
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
      {acao && (
        <FormularioAcaoOrdem
          key={`${acao.ordem.id}-${acao.acao}`}
          acao={acao.acao}
          enviando={mutacao.isPending}
          erro={erro}
          focoAoFechar={focoAoFechar}
          aoFechar={() => setAcao(null)}
          aoEnviar={(valores) =>
            mutacao.mutate({ acaoSelecionada: acao, valores })
          }
        />
      )}
    </>
  )
}
