import type { ReactNode } from 'react'
import { AlertTriangle, ListFilter } from 'lucide-react'
import { Etiqueta } from '@/components/Etiqueta'
import { Esqueleto, TEXTO_DADOS_INDISPONIVEIS } from '@/components/Estados'

export interface Destaque {
  inicio: number
  fim: number
}

export interface ItemInsight {
  texto: string
  etiqueta?: string
  // Posições, no texto, dos números que a observação cita e o backend conferiu.
  destaques?: ReadonlyArray<Destaque>
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

// Pela posição: buscar o trecho "25" no texto marcaria também o fim de "2025".
function comDestaques(texto: string, destaques: ReadonlyArray<Destaque> = []) {
  const ordenados = destaques
    .filter(({ inicio, fim }) => inicio >= 0 && inicio < fim && fim <= texto.length)
    .sort((a, b) => a.inicio - b.inicio)
  const partes: ReactNode[] = []
  let cursor = 0
  for (const { inicio, fim } of ordenados) {
    if (inicio < cursor) {
      continue
    }
    partes.push(
      texto.slice(cursor, inicio),
      <strong key={inicio} className="ve-insight-num">
        {texto.slice(inicio, fim)}
      </strong>,
    )
    cursor = fim
  }
  return partes.length === 0 ? texto : [...partes, texto.slice(cursor)]
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
