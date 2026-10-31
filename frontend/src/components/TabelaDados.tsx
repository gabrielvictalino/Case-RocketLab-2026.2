import { useState, type ReactNode } from 'react'
import { flexRender, type SortingState } from '@tanstack/react-table'
import {
  getCoreRowModel,
  getSortedRowModel,
  useLegacyTable,
  type LegacyColumnDef,
} from '@tanstack/react-table/legacy'
import {
  Esqueleto,
  EstadoErro,
  EstadoIndisponivel,
  EstadoVazio,
} from '@/components/Estados'

export type ColunaTabela<T extends object, TValue = unknown> = LegacyColumnDef<
  T,
  TValue
>

export interface MetaColunaTabela {
  alinhamento?: 'esquerda' | 'direita'
}

export interface TabelaDadosProps<T extends object> {
  colunas: ColunaTabela<T, unknown>[]
  dados: T[]
  legenda: string
  chaveLinha?: (linha: T, indice: number) => string
  aoClicarLinha?: (linha: T) => void
  ordenacaoInicial?: SortingState
  carregando?: boolean
  erro?: string | null
  aoTentarNovamente?: () => void
  indisponivel?: boolean
  tituloVazio?: string
  mensagemVazio?: string
  rodape?: ReactNode
}

export function TabelaDados<T extends object>({
  colunas,
  dados,
  legenda,
  chaveLinha,
  aoClicarLinha,
  ordenacaoInicial = [],
  carregando = false,
  erro = null,
  aoTentarNovamente,
  indisponivel = false,
  tituloVazio,
  mensagemVazio,
  rodape,
}: TabelaDadosProps<T>) {
  const [sorting, setSorting] = useState<SortingState>(ordenacaoInicial)

  const tabela = useLegacyTable({
    data: dados,
    columns: colunas,
    defaultColumn: {
      sortDescFirst: false,
    },
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getRowId: chaveLinha,
  })

  if (indisponivel) {
    return (
      <div className="ve-table-root">
        <div className="ve-table-wrap">
          <EstadoIndisponivel compacto />
        </div>
      </div>
    )
  }

  if (carregando) {
    return (
      <div className="ve-table-root">
        <div className="ve-table-wrap" style={{ padding: 'var(--space-4)' }}>
          <Esqueleto linhas={5} altura={14} />
        </div>
      </div>
    )
  }

  if (erro) {
    return (
      <div className="ve-table-root">
        <div className="ve-table-wrap">
          <EstadoErro
            mensagem={erro}
            compacto
            aoTentarNovamente={aoTentarNovamente}
          />
        </div>
      </div>
    )
  }

  if (dados.length === 0) {
    return (
      <div className="ve-table-root">
        <div className="ve-table-wrap">
          <EstadoVazio
            titulo={tituloVazio}
            mensagem={mensagemVazio}
            compacto
          />
        </div>
      </div>
    )
  }

  return (
    <div className="ve-table-root">
      <div className="ve-table-wrap">
        <table className="ve-table">
          <caption className="ve-sr">{legenda}</caption>
          <thead>
            {tabela.getHeaderGroups().map((grupo) => (
              <tr key={grupo.id}>
                {grupo.headers.map((header) => {
                  const meta = header.column.columnDef.meta as
                    | MetaColunaTabela
                    | undefined
                  const direita = meta?.alinhamento === 'direita'
                  const podeOrdenar = header.column.getCanSort()
                  const direcao = header.column.getIsSorted()
                  const ariaSort =
                    direcao === 'asc'
                      ? 'ascending'
                      : direcao === 'desc'
                        ? 'descending'
                        : undefined

                  return (
                    <th
                      key={header.id}
                      scope="col"
                      aria-sort={ariaSort}
                      className={direita ? 've-right' : undefined}
                    >
                      {header.isPlaceholder ? null : podeOrdenar ? (
                        <button
                          type="button"
                          className="ve-th-sort"
                          aria-sort={ariaSort}
                          onClick={header.column.getToggleSortingHandler()}
                        >
                          <span>
                            {flexRender(
                              header.column.columnDef.header,
                              header.getContext(),
                            )}
                          </span>
                          <span aria-hidden="true">
                            {direcao === 'asc'
                              ? '↑'
                              : direcao === 'desc'
                                ? '↓'
                                : '↕'}
                          </span>
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )
                      )}
                    </th>
                  )
                })}
              </tr>
            ))}
          </thead>
          <tbody>
            {tabela.getRowModel().rows.map((linha) => {
              const clicavel = Boolean(aoClicarLinha)
              return (
                <tr
                  key={linha.id}
                  onClick={
                    aoClicarLinha
                      ? () => aoClicarLinha(linha.original)
                      : undefined
                  }
                  style={clicavel ? { cursor: 'pointer' } : undefined}
                >
                  {linha.getVisibleCells().map((celula) => {
                    const meta = celula.column.columnDef.meta as
                      | MetaColunaTabela
                      | undefined
                    const direita = meta?.alinhamento === 'direita'
                    return (
                      <td
                        key={celula.id}
                        className={direita ? 've-right' : undefined}
                      >
                        {flexRender(
                          celula.column.columnDef.cell,
                          celula.getContext(),
                        )}
                      </td>
                    )
                  })}
                </tr>
              )
            })}
          </tbody>
        </table>
        {rodape && <div className="ve-table-foot">{rodape}</div>}
      </div>
    </div>
  )
}
