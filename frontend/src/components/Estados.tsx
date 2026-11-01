import type { ReactNode } from 'react'
import { AlertCircle, Clock, Inbox } from 'lucide-react'

export const TEXTO_DADOS_INDISPONIVEIS =
  'Dados ainda não disponíveis nesta versão do portal.'

export interface EstadoIndisponivelProps {
  titulo?: string
  mensagem?: string
  compacto?: boolean
}

export function EstadoIndisponivel({
  titulo = 'Dados indisponíveis',
  mensagem = TEXTO_DADOS_INDISPONIVEIS,
  compacto = false,
}: EstadoIndisponivelProps) {
  return (
    <div
      className={`ve-empty ve-empty-attention ${compacto ? 've-empty-compact' : ''}`}
      role="status"
    >
      <span className="ve-empty-icon" aria-hidden="true">
        <Clock size={18} />
      </span>
      <div>
        <p className="ve-empty-title">{titulo}</p>
        <p className="ve-empty-text">{mensagem}</p>
      </div>
    </div>
  )
}

export interface EstadoVazioProps {
  titulo?: string
  mensagem?: string
  compacto?: boolean
  acao?: ReactNode
}

export function EstadoVazio({
  titulo = 'Nenhum registro encontrado',
  mensagem = 'Não há dados para os filtros selecionados.',
  compacto = false,
  acao,
}: EstadoVazioProps) {
  return (
    <div className={`ve-empty ${compacto ? 've-empty-compact' : ''}`} role="status">
      <span className="ve-empty-icon" aria-hidden="true">
        <Inbox size={18} />
      </span>
      <div>
        <p className="ve-empty-title">{titulo}</p>
        <p className="ve-empty-text">{mensagem}</p>
        {acao && <div style={{ marginTop: 'var(--space-2)' }}>{acao}</div>}
      </div>
    </div>
  )
}

export interface EstadoErroProps {
  titulo?: string
  mensagem: string
  compacto?: boolean
  aoTentarNovamente?: () => void
}

export function EstadoErro({
  titulo = 'Não foi possível carregar os dados',
  mensagem,
  compacto = false,
  aoTentarNovamente,
}: EstadoErroProps) {
  return (
    <div
      className={`ve-empty ve-empty-error ${compacto ? 've-empty-compact' : ''}`}
      role="alert"
    >
      <span className="ve-empty-icon" aria-hidden="true">
        <AlertCircle size={18} />
      </span>
      <div>
        <p className="ve-empty-title">{titulo}</p>
        <p className="ve-empty-text">{mensagem}</p>
        {aoTentarNovamente && (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <button
              type="button"
              className="ve-btn ve-btn-sm"
              onClick={aoTentarNovamente}
            >
              Tentar novamente
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export interface EsqueletoProps {
  linhas?: number
  altura?: number
  className?: string
}

export function Esqueleto({ linhas = 3, altura = 14, className = '' }: EsqueletoProps) {
  return (
    <div
      role="status"
      aria-label="Carregando dados"
      className={`ve-stack ${className}`}
      style={{ padding: 'var(--space-3) 0' }}
    >
      {Array.from({ length: linhas }).map((_, idx) => (
        <div
          key={idx}
          style={{
            height: `${altura}px`,
            width: idx === linhas - 1 && linhas > 1 ? '68%' : '100%',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--surface-sunken)',
          }}
        />
      ))}
    </div>
  )
}
