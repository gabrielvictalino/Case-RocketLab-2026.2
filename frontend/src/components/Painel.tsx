import type { ReactNode } from 'react'

export interface PainelProps {
  titulo?: ReactNode
  subtitulo?: ReactNode
  acoes?: ReactNode
  preencher?: boolean
  className?: string
  children: ReactNode
}

export function Painel({
  titulo,
  subtitulo,
  acoes,
  preencher = false,
  className = '',
  children,
}: PainelProps) {
  return (
    <section
      className={`ve-panel ${preencher ? 've-panel-fill' : ''} ${className}`.trim()}
    >
      {(titulo || subtitulo || acoes) && (
        <div className="ve-panel-head">
          <div>
            {titulo && <h2 className="ve-panel-title">{titulo}</h2>}
            {subtitulo && <p className="ve-panel-sub">{subtitulo}</p>}
          </div>
          {acoes && <div className="ve-panel-actions">{acoes}</div>}
        </div>
      )}
      {children}
    </section>
  )
}
