import { useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { Button } from '@/components/ui/button'
import { formatarCompetencia } from '@/lib/formatacao'
import {
  ajustarFimPeriodo,
  ajustarInicioPeriodo,
  listarCompetencias,
  resolverPeriodos,
  serializarPeriodo,
} from '@/lib/periodos'

const CLASSES_SELECT =
  'border-input bg-background text-foreground focus-visible:border-ring focus-visible:ring-ring/50 h-8 rounded-md border px-2 text-xs font-medium shadow-xs outline-none focus-visible:ring-[3px] disabled:cursor-not-allowed disabled:opacity-50'

export function BarraPeriodo() {
  const {
    carga,
    limites,
    carregando,
    erro,
    periodo,
    comparacao,
    definirPeriodo,
    definirComparacao,
    aplicarPadrao,
    aplicarPrimeiroAno,
  } = usePeriodo()
  const [searchParams, setSearchParams] = useSearchParams()

  useEffect(() => {
    if (!limites) {
      return
    }
    const resolvido = resolverPeriodos(searchParams, limites)
    if (!resolvido.normalizado) {
      return
    }
    const proximo = new URLSearchParams(searchParams)
    proximo.set('periodo', serializarPeriodo(resolvido.periodo))
    if (resolvido.comparacao) {
      proximo.set('comparacao', serializarPeriodo(resolvido.comparacao))
    } else {
      proximo.delete('comparacao')
    }
    setSearchParams(proximo, { replace: true })
  }, [limites, searchParams, setSearchParams])

  const opcoesCompetencia = useMemo(() => {
    if (!limites) {
      return []
    }
    return listarCompetencias(limites)
  }, [limites])

  if (erro) {
    const mensagemErro =
      erro.status === 503 || erro.code === 'BASE_INDISPONIVEL'
        ? 'Nenhuma carga publicada'
        : erro.message
    return (
      <div
        role="status"
        className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs"
      >
        <span className="font-medium">{mensagemErro}</span>
      </div>
    )
  }

  if (carregando || !carga || !limites || !periodo) {
    return (
      <div className="text-muted-foreground flex items-center gap-2 text-xs">
        <span>Carregando período...</span>
      </div>
    )
  }

  return (
    <div className="flex flex-1 flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground text-xs font-medium">
            Período
          </span>
          <select
            aria-label="Início do período"
            className={CLASSES_SELECT}
            value={periodo.inicio}
            onChange={(e) =>
              definirPeriodo(ajustarInicioPeriodo(periodo, e.target.value))
            }
          >
            {opcoesCompetencia.map((comp) => (
              <option key={comp} value={comp}>
                {formatarCompetencia(comp)}
              </option>
            ))}
          </select>
          <span className="text-muted-foreground text-xs">até</span>
          <select
            aria-label="Fim do período"
            className={CLASSES_SELECT}
            value={periodo.fim}
            onChange={(e) =>
              definirPeriodo(ajustarFimPeriodo(periodo, e.target.value))
            }
          >
            {opcoesCompetencia.map((comp) => (
              <option key={comp} value={comp}>
                {formatarCompetencia(comp)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-muted-foreground text-xs font-medium">
            Comparação
          </span>
          <select
            aria-label="Início da comparação"
            className={CLASSES_SELECT}
            value={comparacao?.inicio ?? ''}
            onChange={(e) => {
              const valor = e.target.value
              if (!valor) return
              const baseComp = comparacao ?? { inicio: valor, fim: valor }
              definirComparacao(ajustarInicioPeriodo(baseComp, valor))
            }}
          >
            {!comparacao ? (
              <option value="" disabled>
                Sem comparação
              </option>
            ) : null}
            {opcoesCompetencia.map((comp) => (
              <option key={comp} value={comp}>
                {formatarCompetencia(comp)}
              </option>
            ))}
          </select>
          <span className="text-muted-foreground text-xs">até</span>
          <select
            aria-label="Fim da comparação"
            className={CLASSES_SELECT}
            value={comparacao?.fim ?? ''}
            onChange={(e) => {
              const valor = e.target.value
              if (!valor) return
              const baseComp = comparacao ?? { inicio: valor, fim: valor }
              definirComparacao(ajustarFimPeriodo(baseComp, valor))
            }}
          >
            {!comparacao ? (
              <option value="" disabled>
                Sem comparação
              </option>
            ) : null}
            {opcoesCompetencia.map((comp) => (
              <option key={comp} value={comp}>
                {formatarCompetencia(comp)}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-center gap-1.5">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={aplicarPadrao}
          >
            Padrão
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={aplicarPrimeiroAno}
          >
            Primeiro ano × Últimos 12 meses
          </Button>
        </div>
      </div>

      <div className="text-muted-foreground flex flex-wrap items-center gap-2 text-xs">
        <span>Dados até {formatarCompetencia(limites.maisRecente)}</span>
        <span aria-hidden="true">·</span>
        <span title={`Contrato ${carga.versao_contrato}`}>
          {carga.batch_id} ({carga.versao_contrato})
        </span>
        {carga.sintetica ? (
          <span className="bg-secondary text-secondary-foreground rounded px-1.5 py-0.5 text-[11px] font-medium">
            amostra sintética
          </span>
        ) : null}
      </div>
    </div>
  )
}
