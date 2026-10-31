import type { ReactNode } from 'react'

export interface CabecalhoPaginaProps {
  titulo: string
  subtitulo?: ReactNode
  acoes?: ReactNode
}

export function CabecalhoPagina({
  titulo,
  subtitulo,
  acoes,
}: CabecalhoPaginaProps) {
  return (
    <header
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        alignItems: 'flex-end',
        justifyContent: 'space-between',
        gap: '12px',
      }}
    >
      <div>
        <h1
          style={{
            margin: 0,
            fontSize: '26px',
            lineHeight: '32px',
            fontWeight: 600,
            letterSpacing: '-0.01em',
          }}
        >
          {titulo}
        </h1>
        {subtitulo && (
          <p
            style={{
              margin: '4px 0 0',
              fontSize: '13px',
              lineHeight: '18px',
              color: 'var(--ink-muted)',
            }}
          >
            {subtitulo}
          </p>
        )}
      </div>
      {acoes && <div className="ve-row">{acoes}</div>}
    </header>
  )
}
