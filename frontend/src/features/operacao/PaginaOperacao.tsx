
import { Info, RotateCcw, SlidersHorizontal } from 'lucide-react'
import { useSearchParams } from 'react-router'

type Ordenacao = 'chi' | 'dec' | 'fec'

const colunasRanking = [
  'Alimentador',
  'Município',
  'CHI',
  'DEC',
  'FEC',
  'UCs',
  'Causa principal',
]

function CartaoIndicador({
  titulo,
  unidade,
}: {
  titulo: string
  unidade: string
}) {
  return (
    <article className="rounded-lg border bg-card p-5">
      <p className="text-sm font-medium text-muted-foreground">
        {titulo}
      </p>

      <div className="mt-3 flex items-baseline gap-2">
        <span className="text-3xl font-semibold tabular-nums">—</span>
        <span className="text-sm text-muted-foreground">{unidade}</span>
      </div>

      <p className="mt-3 text-xs text-muted-foreground">
        Dados indisponíveis
      </p>
    </article>
  )
}

function CartaoGrafico({
  titulo,
  unidade,
}: {
  titulo: string
  unidade: string
}) {
  return (
    <article className="rounded-lg border bg-card p-5">
      <h3 className="font-semibold">{titulo}</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Evolução por competência · {unidade}
      </p>

      <div className="mt-5 flex min-h-56 items-center justify-center rounded-md border border-dashed bg-muted/20 px-5 text-center">
        <div className="max-w-xs space-y-2">
          <p className="text-sm font-medium">Série indisponível</p>
          <p className="text-sm text-muted-foreground">
            A evolução mensal será apresentada após a integração
            com a API de continuidade.
          </p>
        </div>
      </div>
    </article>
  )
}

export function PaginaOperacao() {
  const [searchParams, setSearchParams] = useSearchParams()

  const incluirAtipicos = searchParams.get('atipicos') !== 'false'

  const parametroOrdenacao = searchParams.get('ordenar')

  const ordenacao: Ordenacao =
    parametroOrdenacao === 'dec' || parametroOrdenacao === 'fec'
      ? parametroOrdenacao
      : 'chi'

  function atualizarParametro(chave: string, valor: string) {
    setSearchParams((anteriores) => {
      const proximos = new URLSearchParams(anteriores)
      proximos.set(chave, valor)
      return proximos
    })
  }

  function limparFiltros() {
    setSearchParams((anteriores) => {
      const proximos = new URLSearchParams(anteriores)

      proximos.delete('atipicos')
      proximos.delete('ordenar')
      proximos.delete('municipio')
      proximos.delete('alimentador')

      return proximos
    })
  }

  return (
    <section className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Operação
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Continuidade do fornecimento e desempenho dos alimentadores
        </p>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">
            Indicadores de continuidade
          </h2>
          <p className="text-sm text-muted-foreground">
            Acompanhamento de DEC e FEC por competência
          </p>
        </div>

        <span className="rounded-md border px-3 py-1.5 text-xs text-muted-foreground">
          Aguardando dados de continuidade
        </span>
      </div>

      <div className="rounded-lg border bg-card p-5">
        <div className="mb-4 flex items-center gap-2">
          <SlidersHorizontal
            className="h-4 w-4 text-muted-foreground"
            aria-hidden="true"
          />
          <h3 className="text-sm font-semibold">Filtros</h3>
        </div>

        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2">
            <label
              htmlFor="operacao-municipio"
              className="block text-sm font-medium"
            >
              Município
            </label>
            <select
              id="operacao-municipio"
              disabled
              defaultValue=""
              className="h-10 w-full rounded-md border bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="">Aguardando municípios</option>
            </select>
          </div>

          <div className="space-y-2">
            <label
              htmlFor="operacao-alimentador"
              className="block text-sm font-medium"
            >
              Alimentador
            </label>
            <select
              id="operacao-alimentador"
              disabled
              defaultValue=""
              className="h-10 w-full rounded-md border bg-background px-3 text-sm disabled:cursor-not-allowed disabled:opacity-60"
            >
              <option value="">Aguardando alimentadores</option>
            </select>
          </div>

          <div className="flex items-end">
            <label className="flex min-h-10 w-full cursor-pointer items-center justify-between gap-3 rounded-md border px-3">
              <span className="text-sm font-medium">
                Incluir eventos atípicos
              </span>
              <input
                type="checkbox"
                checked={incluirAtipicos}
                onChange={(evento) =>
                  atualizarParametro(
                    'atipicos',
                    String(evento.target.checked),
                  )
                }
                className="h-4 w-4 accent-foreground"
              />
            </label>
          </div>

          <div className="flex items-end">
            <button
              type="button"
              onClick={limparFiltros}
              className="flex h-10 w-full items-center justify-center gap-2 rounded-md border bg-background px-3 text-sm font-medium transition-colors hover:bg-muted"
            >
              <RotateCcw className="h-4 w-4" aria-hidden="true" />
              Limpar filtros
            </button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <CartaoIndicador titulo="DEC" unidade="horas" />
        <CartaoIndicador titulo="FEC" unidade="interrupções" />
        <CartaoIndicador
          titulo="Eventos atípicos"
          unidade="eventos"
        />
      </div>

      <div
        role="note"
        className="flex items-start gap-3 rounded-lg border bg-muted/40 p-4 text-sm"
      >
        <Info
          className="mt-0.5 h-4 w-4 shrink-0"
          aria-hidden="true"
        />
        <p>
          Os valores apresentados são comparativos entre períodos e
          não devem ser comparados aos limites regulatórios da ANEEL.
        </p>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <CartaoGrafico
          titulo="DEC por competência"
          unidade="horas"
        />
        <CartaoGrafico
          titulo="FEC por competência"
          unidade="interrupções"
        />
      </div>

      <div className="overflow-hidden rounded-lg border bg-card">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b p-5">
          <div>
            <h2 className="font-semibold">
              Ranking de alimentadores
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Alimentadores com maior impacto na continuidade
            </p>
          </div>

          <div className="space-y-2">
            <label
              htmlFor="operacao-ordenacao"
              className="block text-xs font-medium text-muted-foreground"
            >
              Ordenar por
            </label>
            <select
              id="operacao-ordenacao"
              value={ordenacao}
              onChange={(evento) =>
                atualizarParametro('ordenar', evento.target.value)
              }
              className="h-10 min-w-36 rounded-md border bg-background px-3 text-sm"
            >
              <option value="chi">CHI (padrão)</option>
              <option value="dec">DEC</option>
              <option value="fec">FEC</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                {colunasRanking.map((coluna) => (
                  <th
                    key={coluna}
                    scope="col"
                    className="whitespace-nowrap px-5 py-3 font-medium"
                  >
                    {coluna}
                  </th>
                ))}
              </tr>
            </thead>

            <tbody>
              <tr>
                <td
                  colSpan={colunasRanking.length}
                  className="px-5 py-12 text-center"
                >
                  <p className="font-medium">
                    Nenhum dado disponível
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground">
                    O ranking será exibido após a integração
                    dos dados de continuidade.
                  </p>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}
