import { AlertTriangle, ListFilter } from 'lucide-react'
import { Etiqueta } from '@/components/Etiqueta'
import { Esqueleto, TEXTO_DADOS_INDISPONIVEIS } from '@/components/Estados'

export interface ItemInsight {
  texto: string
  etiqueta?: string
  // Trechos do texto mostrados em destaque: os números que a observação cita.
  destaques?: ReadonlyArray<string>
}

export interface BlocoInsightProps {
  titulo?: string
  meta?: string
  itens?: ReadonlyArray<ItemInsight>
  carregando?: boolean
  mensagemCarregando?: string
  indisponivel?: boolean
  tituloIndisponivel?: string
  mensagemIndisponivel?: string
  rodape?: string
}

function escaparRegex(texto: string) {
  return texto.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function comDestaques(texto: string, destaques: ReadonlyArray<string> = []) {
  const trechos = [...new Set(destaques.filter(Boolean))].sort((a, b) => b.length - a.length)
  if (trechos.length === 0) {
    return texto
  }
  const padrao = new RegExp(`(${trechos.map(escaparRegex).join('|')})`)
  return texto.split(padrao).map((parte, idx) =>
    idx % 2 === 1 ? (
      <strong key={idx} className="ve-insight-num">
        {parte}
      </strong>
    ) : (
      parte
    ),
  )
}

export function BlocoInsight({
  titulo = 'Insight do período',
  meta,
  itens = [],
  carregando = false,
  mensagemCarregando,
  indisponivel = false,
  tituloIndisponivel = 'Síntese indisponível',
  mensagemIndisponivel = TEXTO_DADOS_INDISPONIVEIS,
  rodape,
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
            <strong>{tituloIndisponivel}</strong>
            {' · '}
            <span>{mensagemIndisponivel}</span>
          </div>
        </div>
      ) : carregando ? (
        <>
          {mensagemCarregando && <p className="ve-insight-meta">{mensagemCarregando}</p>}
          <Esqueleto linhas={4} altura={14} />
        </>
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
                {comDestaques(item.texto, item.destaques)}
              </span>
              {item.etiqueta && <Etiqueta>{item.etiqueta}</Etiqueta>}
            </li>
          ))}
        </ol>
      )}
      {rodape && !indisponivel && !carregando && <p className="ve-insight-foot">{rodape}</p>}
    </section>
  )
}
