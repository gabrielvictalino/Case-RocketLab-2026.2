import { AlertTriangle, MessageSquareText, Send, X } from 'lucide-react'
import { useLocation } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'

export interface PainelAgenteProps {
  aberto: boolean
  aoFechar: () => void
}

const ROTULO_ROTA: Record<string, string> = {
  '/visao-geral': 'Visão Geral',
  '/receita': 'Receita',
  '/unidade-consumidora': 'Unidade Consumidora',
  '/perdas': 'Perdas',
  '/operacao': 'Operação',
}

export function PainelAgente({ aberto, aoFechar }: PainelAgenteProps) {
  const location = useLocation()
  const { periodo, comparacao } = usePeriodo()

  if (!aberto) {
    return null
  }

  const nomeTela = ROTULO_ROTA[location.pathname] ?? 'Portal'
  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const rotuloComparacao = comparacao
    ? formatarIntervaloPeriodo(comparacao)
    : null
  const contextoPeriodo = rotuloPeriodo
    ? rotuloComparacao
      ? `${rotuloPeriodo} × ${rotuloComparacao}`
      : rotuloPeriodo
    : 'período atual'

  return (
    <aside
      className="ve-agent"
      role="dialog"
      aria-label="Pergunte aos dados"
    >
      <div className="ve-agent-head">
        <div>
          <div className="ve-agent-title">
            <MessageSquareText
              size={16}
              className="ve-icon"
              aria-hidden="true"
            />
            <span>Pergunte aos dados</span>
          </div>
          <div
            className="ve-muted"
            style={{ fontSize: '12px', lineHeight: '16px', marginTop: '2px' }}
          >
            {nomeTela} · {contextoPeriodo}
          </div>
        </div>
        <button
          type="button"
          className="ve-btn ve-btn-quiet ve-btn-sm"
          aria-label="Fechar painel do agente"
          onClick={aoFechar}
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>

      <div className="ve-agent-body">
        <div className="ve-insight-off" role="status">
          <AlertTriangle size={16} className="ve-icon" aria-hidden="true" />
          <div>
            <strong>Assistente indisponível</strong>
            {' · '}
            <span>
              O agente ainda não está disponível nesta versão do portal.
            </span>
          </div>
        </div>
      </div>

      <form
        className="ve-agent-form"
        onSubmit={(e) => {
          e.preventDefault()
        }}
      >
        <textarea
          rows={1}
          disabled
          placeholder="Pergunte sobre os dados..."
          aria-label="Pergunte sobre os dados"
        />
        <button
          type="submit"
          disabled
          className="ve-btn ve-btn-primary"
          aria-label="Enviar pergunta"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      </form>
    </aside>
  )
}
