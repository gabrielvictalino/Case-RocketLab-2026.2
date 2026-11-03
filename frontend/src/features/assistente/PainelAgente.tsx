import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { AlertTriangle, MessageSquareText, RotateCcw, Send, X } from 'lucide-react'
import { useLocation, useSearchParams } from 'react-router'
import { usePeriodo } from '@/app/periodo/usePeriodo'
import { Etiqueta } from '@/components/Etiqueta'
import {
  contextoDaTela,
  ROTULO_TELA,
  rotulosDosRecortes,
} from '@/features/assistente/conversa'
import { EtapasEspera, RespostaAgente } from '@/features/assistente/RespostaAgente'
import type { ConversaAgente } from '@/features/assistente/useConversaAgente'
import { formatarIntervaloPeriodo } from '@/lib/formatacao'

const LIMITE_PERGUNTA = 1000

const SUGESTOES = [
  'Qual bairro mais perdeu volume residencial no último ano?',
  'Quantas unidades com painel solar em Olinda tiveram queda de consumo acima de 30%?',
  'Quais os 5 alimentadores com o pior DEC no último ano?',
]

export interface PainelAgenteProps {
  aberto: boolean
  aoFechar: () => void
  conversa: ConversaAgente
}

export function PainelAgente({ aberto, aoFechar, conversa }: PainelAgenteProps) {
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { periodo, comparacao, parametros } = usePeriodo()
  const [texto, setTexto] = useState('')
  const fimDaConversa = useRef<HTMLDivElement>(null)
  const { trocas, aguardando, perguntar, novaConversa } = conversa

  useEffect(() => {
    fimDaConversa.current?.scrollIntoView?.({ block: 'end' })
  }, [trocas])

  if (!aberto) {
    return null
  }

  const contexto = contextoDaTela(location.pathname, searchParams, parametros)
  const nomeTela = contexto.tela ? ROTULO_TELA[contexto.tela] : 'Portal'
  const rotuloPeriodo = periodo ? formatarIntervaloPeriodo(periodo) : null
  const rotuloComparacao = comparacao ? formatarIntervaloPeriodo(comparacao) : null
  const contextoPeriodo = rotuloPeriodo
    ? rotuloComparacao
      ? `${rotuloPeriodo} × ${rotuloComparacao}`
      : rotuloPeriodo
    : 'período atual'
  const recortes = rotulosDosRecortes(contexto)

  function enviar(pergunta: string) {
    if (aguardando || !pergunta.trim()) {
      return
    }
    perguntar(pergunta, contexto)
    setTexto('')
  }

  function aoTeclar(evento: KeyboardEvent<HTMLTextAreaElement>) {
    if (evento.key === 'Enter' && !evento.shiftKey) {
      evento.preventDefault()
      enviar(texto)
    }
  }

  return (
    <aside className="ve-agent" role="dialog" aria-label="Pergunte aos dados">
      <div className="ve-agent-head">
        <div style={{ minWidth: 0 }}>
          <div className="ve-agent-title">
            <MessageSquareText size={16} className="ve-icon" aria-hidden="true" />
            <span>Pergunte aos dados</span>
          </div>
          <div className="ve-muted ve-agent-context" aria-label="Contexto enviado">
            {nomeTela} · {contextoPeriodo}
          </div>
          {recortes.length > 0 && (
            <div className="ve-agent-chips" aria-label="Recortes da tela">
              {recortes.map((recorte) => (
                <Etiqueta key={recorte}>{recorte}</Etiqueta>
              ))}
            </div>
          )}
        </div>
        <div style={{ display: 'flex', gap: 'var(--space-1)', flex: 'none' }}>
          {trocas.length > 0 && (
            <button
              type="button"
              className="ve-btn ve-btn-quiet ve-btn-sm"
              aria-label="Começar uma nova conversa"
              title="Nova conversa"
              disabled={aguardando}
              onClick={novaConversa}
            >
              <RotateCcw size={16} aria-hidden="true" />
            </button>
          )}
          <button
            type="button"
            className="ve-btn ve-btn-quiet ve-btn-sm"
            aria-label="Fechar painel do agente"
            onClick={aoFechar}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>
      </div>

      <div className="ve-agent-body" aria-live="polite">
        {trocas.length === 0 && (
          <div className="ve-agent-intro">
            <p>
              Pergunte em português sobre consumo, receita, interrupções, atendimentos,
              geração distribuída e perdas. A resposta mostra o período, a métrica e o SQL
              usados. Quando os dados não respondem, o agente diz que não sabe.
            </p>
            <div className="ve-agent-sugestoes">
              {SUGESTOES.map((sugestao) => (
                <button
                  key={sugestao}
                  type="button"
                  className="ve-btn ve-btn-sm"
                  onClick={() => enviar(sugestao)}
                >
                  {sugestao}
                </button>
              ))}
            </div>
          </div>
        )}
        {trocas.map((troca) => (
          <div key={troca.id} className="ve-agent-troca">
            <p className="ve-agent-q">{troca.pergunta}</p>
            {troca.estado === 'pendente' && <EtapasEspera />}
            {troca.estado === 'falhou' && (
              <div className="ve-insight-off" role="alert">
                <AlertTriangle size={16} className="ve-icon" aria-hidden="true" />
                <span>{troca.erro}</span>
              </div>
            )}
            {troca.estado === 'respondida' && troca.resposta && (
              <RespostaAgente resposta={troca.resposta} aoPerguntar={enviar} />
            )}
          </div>
        ))}
        <div ref={fimDaConversa} />
      </div>

      <form
        className="ve-agent-form"
        onSubmit={(evento) => {
          evento.preventDefault()
          enviar(texto)
        }}
      >
        <textarea
          rows={1}
          value={texto}
          maxLength={LIMITE_PERGUNTA}
          onChange={(evento) => setTexto(evento.target.value)}
          onKeyDown={aoTeclar}
          placeholder="Pergunte sobre os dados..."
          aria-label="Pergunte sobre os dados"
        />
        <button
          type="submit"
          disabled={aguardando || !texto.trim()}
          className="ve-btn ve-btn-primary"
          aria-label="Enviar pergunta"
        >
          <Send size={16} aria-hidden="true" />
        </button>
      </form>
    </aside>
  )
}
