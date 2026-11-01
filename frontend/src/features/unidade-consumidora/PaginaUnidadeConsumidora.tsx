
import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { useNavigate, useParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { normalizarIdentificadorUC } from './logicaUnidadeConsumidora'

export function PaginaUnidadeConsumidora() {
  const navigate = useNavigate()
  const { id } = useParams<{ id: string }>()

  const identificadorDaRota = id
    ? normalizarIdentificadorUC(id)
    : null

  const [busca, setBusca] = useState(id ?? '')
  const [erroBusca, setErroBusca] = useState('')

  function buscarUnidade(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()

    const identificador = normalizarIdentificadorUC(busca)

    if (!identificador) {
      setErroBusca('Informe um número de UC válido.')
      return
    }

    setErroBusca('')
    navigate(`/ucs/${identificador}`)
  }

  return (
    <section className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-2">
          <h1 className="text-2xl font-semibold tracking-tight">
            Unidade Consumidora
          </h1>
          <p className="text-sm text-muted-foreground">
            Consulte as informações de uma unidade consumidora.
          </p>
        </div>

        <form
          onSubmit={buscarUnidade}
          className="flex w-full max-w-md flex-col gap-2"
        >
          <label
            htmlFor="busca-uc"
            className="text-sm font-medium"
          >
            Número da UC
          </label>

          <div className="flex gap-2">
            <input
              id="busca-uc"
              type="text"
              value={busca}
              onChange={(evento) => {
                setBusca(evento.target.value)
                setErroBusca('')
              }}
              placeholder="Ex.: UC100123"
              aria-invalid={Boolean(erroBusca)}
              aria-describedby={
                erroBusca ? 'erro-busca-uc' : 'ajuda-busca-uc'
              }
              className="h-9 min-w-0 flex-1 rounded-md border border-input bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />

            <Button type="submit">
              <Search className="size-4" />
              Buscar
            </Button>
          </div>

          {erroBusca ? (
            <p
              id="erro-busca-uc"
              role="alert"
              className="text-sm text-destructive"
            >
              {erroBusca}
            </p>
          ) : (
            <p
              id="ajuda-busca-uc"
              className="text-xs text-muted-foreground"
            >
              Aceita UC100123, uc100123 ou 100123.
            </p>
          )}
        </form>
      </div>

      <p className="text-sm text-muted-foreground">
        Esta tela ignora o período global e mostra sempre os últimos
        12 meses da UC.
      </p>

      {id ? (
        identificadorDaRota ? (
          <div className="rounded-lg border bg-card p-6">
            <h2 className="text-lg font-semibold">
              {identificadorDaRota}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              A consulta dos dados desta unidade depende da integração
              com a API de Visão 360 da UC.
            </p>
          </div>
        ) : (
          <div role="alert" className="rounded-lg border bg-card p-6">
            <h2 className="text-lg font-semibold">
              Identificador de UC inválido
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              Confira o número informado e tente novamente.
            </p>
          </div>
        )
      ) : (
        <div className="rounded-lg border bg-card p-8 text-center">
          <Search
            className="mx-auto mb-3 size-6 text-muted-foreground"
            aria-hidden="true"
          />
          <h2 className="font-semibold">
            Consulte uma unidade consumidora
          </h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Informe o número da UC para iniciar a consulta.
          </p>
        </div>
      )}
    </section>
  )
}
