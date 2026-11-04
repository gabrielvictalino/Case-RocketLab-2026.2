import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { Abas } from '@/components/Abas'
import { CabecalhoPagina } from '@/components/CabecalhoPagina'
import { api, desembrulhar, type ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'
import { cargoDaSessao, useSessao } from '@/lib/auth/sessao'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'
import {
  atualizarRecorteUrl,
  lerRecortesUrl,
  limparRecortesUrl,
} from '@/lib/recortes'
import { useFiltrosMeta } from '@/lib/useFiltrosMeta'
import { AbaFila } from './AbaFila'
import { AbaOrdens } from './AbaOrdens'
import { TAMANHO_PAGINA } from './ordens'

type Status = components['schemas']['Ordem']['status']
const statusValidos: Status[] = ['ABERTA', 'EM_CAMPO', 'CONCLUIDA', 'CANCELADA']
export function PaginaPerdas() {
  const [params, setParams] = useSearchParams()
  const { periodo, carga } = usePeriodo()
  const filtros = useFiltrosMeta()
  const sessao = useSessao()
  const recortes = lerRecortesUrl(params)
  const aba = params.get('aba') === 'ordens' ? 'ordens' : 'fila'
  const bruto = params.get('status')
  const status = statusValidos.includes(bruto as Status)
    ? (bruto as Status)
    : null
  const chave = JSON.stringify([
    recortes.municipio,
    recortes.bairro,
    recortes.classe,
  ])
  const [paginaFila, setPaginaFila] = useState({ chave, pagina: 1 })
  const paginaAtualFila = paginaFila.chave === chave ? paginaFila.pagina : 1
  // A página vale apenas para o status escolhido, inclusive no histórico.
  const [paginaOrdens, setPaginaOrdens] = useState<{
    status: Status | null
    pagina: number
  }>({ status, pagina: 1 })
  const paginaAtualOrdens =
    paginaOrdens.status === status ? paginaOrdens.pagina : 1
  const fila = useQuery({
    queryKey: [
      'perdas-fila',
      recortes.municipio,
      recortes.bairro,
      recortes.classe,
      paginaAtualFila,
      TAMANHO_PAGINA,
    ],
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/perdas/fila', {
          params: {
            query: {
              ...(recortes.municipio && { municipio: recortes.municipio }),
              ...(recortes.bairro && { bairro: recortes.bairro }),
              ...(recortes.classe && { classe: recortes.classe }),
              page: paginaAtualFila,
              size: TAMANHO_PAGINA,
            },
          },
        }),
      ),
  })
  const ordens = useQuery({
    queryKey: ['ordens-inspecao', status, paginaAtualOrdens, TAMANHO_PAGINA],
    queryFn: () =>
      desembrulhar(
        api.GET('/api/v1/ordens-inspecao', {
          params: {
            query: { status, page: paginaAtualOrdens, size: TAMANHO_PAGINA },
          },
        }),
      ),
  })
  const mudarStatus = (valor: string) => {
    const proximo = new URLSearchParams(params)
    if (valor) proximo.set('status', valor)
    else proximo.delete('status')
    setParams(proximo)
  }
  const selecionarAba = (valor: string) => {
    const proximo = new URLSearchParams(params)
    if (valor === 'ordens') proximo.set('aba', 'ordens')
    else proximo.delete('aba')
    setParams(proximo)
  }
  const periodoRotulo = periodo ? ` · ${formatarIntervaloPeriodo(periodo)}` : ''
  const subtitulo = carga
    ? `Fila de inspeção pelo score da carga ${carga.batch_id}${periodoRotulo}`
    : `Fila de inspeção e ordens de inspeção${periodoRotulo}`
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <CabecalhoPagina titulo="Perdas" subtitulo={subtitulo} />
      <Abas
        ariaLabel="Seções de perdas"
        abaAtiva={aba}
        aoSelecionar={selecionarAba}
        abas={[
          { id: 'fila', rotulo: 'Fila', contador: fila.data?.total ?? null },
          {
            id: 'ordens',
            rotulo: 'Ordens',
            contador: ordens.data?.total ?? null,
          },
        ]}
      />
      {aba === 'fila' ? (
        <AbaFila
          dados={fila.data}
          atualizado={fila.isSuccess && !fila.isFetching}
          erro={(fila.error as ErroApi | null)?.message ?? null}
          carregando={fila.isLoading}
          recortes={recortes}
          municipios={filtros.data?.municipios ?? []}
          bairros={filtros.data?.bairros?.[recortes.municipio] ?? []}
          classes={filtros.data?.classes ?? []}
          pagina={paginaAtualFila}
          mudarPagina={(pagina) => setPaginaFila({ chave, pagina })}
          mudarFiltro={(campo, valor) =>
            setParams(atualizarRecorteUrl(params, { [campo]: valor }))
          }
          limpar={() =>
            setParams(
              limparRecortesUrl(params, ['municipio', 'bairro', 'classe']),
            )
          }
          podeEscrever={cargoDaSessao(sessao?.token) === 'perdas'}
          verOrdens={() => {
            const proximo = new URLSearchParams(params)
            proximo.set('aba', 'ordens')
            proximo.set('status', 'ABERTA')
            setParams(proximo)
          }}
          refetch={() => {
            void fila.refetch()
          }}
        />
      ) : (
        <AbaOrdens
          dados={ordens.data}
          atualizado={ordens.isSuccess && !ordens.isFetching}
          erro={(ordens.error as ErroApi | null)?.message ?? null}
          carregando={ordens.isLoading}
          status={status}
          mudarStatus={mudarStatus}
          pagina={paginaAtualOrdens}
          mudarPagina={(pagina) => setPaginaOrdens({ status, pagina })}
          podeEscrever={cargoDaSessao(sessao?.token) === 'perdas'}
          refetch={() => {
            void ordens.refetch()
          }}
        />
      )}
    </div>
  )
}
