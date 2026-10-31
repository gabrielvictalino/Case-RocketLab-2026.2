import { useEffect, useMemo } from 'react'
import { Calendar, ChevronDown } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import {
  formatarCompetencia,
  formatarDataPtBr,
} from '@/lib/formatacao'
import {
  ajustarFimPeriodo,
  ajustarInicioPeriodo,
  atalhoPrimeiroAno,
  listarCompetencias,
  periodoPadrao,
  resolverPeriodos,
  serializarPeriodo,
} from '@/lib/periodos'

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
      <header
        aria-label="Período global e metadados da carga"
        className="ve-period"
      >
        <div role="status" className="ve-muted" style={{ fontSize: '12px' }}>
          <span style={{ fontWeight: 500 }}>{mensagemErro}</span>
        </div>
      </header>
    )
  }

  if (carregando || !carga || !limites || !periodo) {
    return (
      <header
        aria-label="Período global e metadados da carga"
        className="ve-period"
      >
        <div className="ve-muted" style={{ fontSize: '12px' }}>
          <span>Carregando período...</span>
        </div>
      </header>
    )
  }

  const padraoEsperado = periodoPadrao(limites)
  const padraoAtivo =
    periodo.inicio === padraoEsperado.periodo.inicio &&
    periodo.fim === padraoEsperado.periodo.fim &&
    (comparacao?.inicio ?? null) ===
      (padraoEsperado.comparacao?.inicio ?? null) &&
    (comparacao?.fim ?? null) === (padraoEsperado.comparacao?.fim ?? null)

  const atalhoEsperado = atalhoPrimeiroAno(limites)
  const atalhoAtivo =
    periodo.inicio === atalhoEsperado.periodo.inicio &&
    periodo.fim === atalhoEsperado.periodo.fim &&
    comparacao?.inicio === atalhoEsperado.comparacao.inicio &&
    comparacao?.fim === atalhoEsperado.comparacao.fim

  return (
    <header
      aria-label="Período global e metadados da carga"
      className="ve-period"
    >
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 'var(--space-2)',
        }}
      >
        <div className="ve-period-field">
          <Calendar
            size={14}
            className="ve-icon"
            style={{ color: 'var(--ink-muted)' }}
            aria-hidden="true"
          />
          <small>Período</small>
          <select
            aria-label="Início do período"
            value={periodo.inicio}
            onChange={(e) =>
              definirPeriodo(ajustarInicioPeriodo(periodo, e.target.value))
            }
            style={{
              border: 0,
              background: 'transparent',
              font: 'inherit',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--ink)',
              cursor: 'pointer',
              appearance: 'none',
            }}
          >
            {opcoesCompetencia.map((comp) => (
              <option key={comp} value={comp}>
                {formatarCompetencia(comp)}
              </option>
            ))}
          </select>
          <span aria-hidden="true" style={{ fontWeight: 600 }}>
            –
          </span>
          <select
            aria-label="Fim do período"
            value={periodo.fim}
            onChange={(e) =>
              definirPeriodo(ajustarFimPeriodo(periodo, e.target.value))
            }
            style={{
              border: 0,
              background: 'transparent',
              font: 'inherit',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--ink)',
              cursor: 'pointer',
              appearance: 'none',
            }}
          >
            {opcoesCompetencia.map((comp) => (
              <option key={comp} value={comp}>
                {formatarCompetencia(comp)}
              </option>
            ))}
          </select>
          <ChevronDown
            size={14}
            className="ve-icon"
            style={{ color: 'var(--ink-muted)' }}
            aria-hidden="true"
          />
        </div>

        <span className="ve-period-vs">vs</span>

        <div className="ve-period-field">
          <small>Comparação</small>
          <select
            aria-label="Início da comparação"
            value={comparacao?.inicio ?? ''}
            onChange={(e) => {
              const valor = e.target.value
              if (!valor) return
              const baseComp = comparacao ?? { inicio: valor, fim: valor }
              definirComparacao(ajustarInicioPeriodo(baseComp, valor))
            }}
            style={{
              border: 0,
              background: 'transparent',
              font: 'inherit',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--ink)',
              cursor: 'pointer',
              appearance: 'none',
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
          <span aria-hidden="true" style={{ fontWeight: 600 }}>
            –
          </span>
          <select
            aria-label="Fim da comparação"
            value={comparacao?.fim ?? ''}
            onChange={(e) => {
              const valor = e.target.value
              if (!valor) return
              const baseComp = comparacao ?? { inicio: valor, fim: valor }
              definirComparacao(ajustarFimPeriodo(baseComp, valor))
            }}
            style={{
              border: 0,
              background: 'transparent',
              font: 'inherit',
              fontSize: '13px',
              fontWeight: 600,
              color: 'var(--ink)',
              cursor: 'pointer',
              appearance: 'none',
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
          <ChevronDown
            size={14}
            className="ve-icon"
            style={{ color: 'var(--ink-muted)' }}
            aria-hidden="true"
          />
        </div>

        <div className="ve-seg" role="group" aria-label="Atalhos de período">
          <button
            type="button"
            aria-pressed={padraoAtivo}
            onClick={aplicarPadrao}
          >
            Mesmo intervalo do ano anterior
          </button>
          <button
            type="button"
            aria-pressed={atalhoAtivo}
            onClick={aplicarPrimeiroAno}
          >
            Primeiro ano × Últimos 12 meses
          </button>
        </div>
      </div>

      <div className="ve-period-meta">
        <div className="ve-row" style={{ gap: 'var(--space-2)' }}>
          <span style={{ color: 'var(--ink)', fontWeight: 500 }}>
            Competência mais recente {formatarCompetencia(limites.maisRecente)}
          </span>
          {carga.sintetica ? (
            <span className="ve-badge ve-badge-attention">
              amostra sintética
            </span>
          ) : null}
        </div>
        <span
          title={carga.versao_contrato}
          style={{ fontFamily: 'var(--font-mono)', fontSize: '11.5px' }}
        >
          Carga {carga.batch_id} · {formatarDataPtBr(carga.carregado_em)}
        </span>
      </div>
    </header>
  )
}
