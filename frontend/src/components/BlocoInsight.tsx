import { AlertTriangle, ListFilter } from 'lucide-react'
import { Etiqueta } from '@/components/Etiqueta'
import { Esqueleto, TEXTO_DADOS_INDISPONIVEIS } from '@/components/Estados'

export interface ItemInsight {
  texto: string
  etiqueta?: string
}

export interface BlocoInsightProps {
  titulo?: string
  meta?: string
  itens?: ReadonlyArray<ItemInsight>
  carregando?: boolean
  indisponivel?: boolean
  mensagemIndisponivel?: string
}

export function BlocoInsight({
  titulo = 'Insight do período',
  meta,
  itens = [],
  carregando = false,
  indisponivel = false,
  mensagemIndisponivel = TEXTO_DADOS_INDISPONIVEIS,
}: BlocoInsightProps) {
  return (
    <section className="ve-insight" aria-label={titulo}>
      <div className="ve-insight-head">
        <h2 className="ve-insight-title">
          <ListFilter size={16} className="ve-icon" aria-hidden="true" />
          <span>{titulo}</span>
        </h2>
        {meta && <span className="ve-insight-meta">{meta}</span>}
      </div>

      {indisponivel ? (
        <div className="ve-insight-off" role="status">
          <AlertTriangle size={16} className="ve-icon" aria-hidden="true" />
          <div>
            <strong>Síntese indisponível</strong>
            {' · '}
            <span>{mensagemIndisponivel}</span>
          </div>
        </div>
      ) : carregando ? (
        <Esqueleto linhas={4} altura={14} />
      ) : (
        <ol>
          {itens.map((item, idx) => (
            <li
              key={idx}
              style={{
                display: 'flex',
                alignItems: 'baseline',
                justifyContent: 'space-between',
                gap: 'var(--space-2)',
              }}
            >
              <span>
                <strong
                  style={{
                    color: 'var(--ink-muted)',
                    fontSize: '12px',
                    marginRight: 'var(--space-2)',
                  }}
                >
                  {idx + 1}
                </strong>
                {item.texto}
              </span>
              {item.etiqueta && <Etiqueta>{item.etiqueta}</Etiqueta>}
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
