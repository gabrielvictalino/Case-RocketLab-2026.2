import type { ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'

export interface BarraRecorteProps {
  children: ReactNode
  aoLimpar?: () => void
  erro?: string | null
  aoTentarNovamente?: () => void
  acoesDireita?: ReactNode
}

export function BarraRecorte({
  children,
  aoLimpar,
  erro,
  aoTentarNovamente,
  acoesDireita,
}: BarraRecorteProps) {
  return (
    <section aria-label="Recortes" className="ve-filterbar">
      <span className="ve-filterbar-title">RECORTE</span>
      {children}
      {erro && (
        <div
          role="alert"
          className="ve-row"
          style={{
            fontSize: '12px',
            color: 'var(--critical)',
            alignSelf: 'center',
          }}
        >
          <AlertCircle size={14} aria-hidden="true" />
          <span>{erro}</span>
          {aoTentarNovamente && (
            <button
              type="button"
              className="ve-btn ve-btn-sm"
              onClick={aoTentarNovamente}
            >
              Tentar novamente
            </button>
          )}
        </div>
      )}
      <div className="ve-filterbar-end">
        {acoesDireita}
        {aoLimpar && (
          <button
            type="button"
            className="ve-btn ve-btn-quiet ve-btn-sm"
            onClick={aoLimpar}
          >
            Limpar filtros
          </button>
        )}
      </div>
    </section>
  )
}
