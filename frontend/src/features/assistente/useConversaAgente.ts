import { useMutation } from '@tanstack/react-query'
import { useCallback, useRef, useState } from 'react'
import { api, desembrulhar, ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'
import {
  mensagemDeErro,
  type ContextoPergunta,
  type Troca,
} from '@/features/assistente/conversa'

type Pergunta = components['schemas']['Pergunta']

export interface ConversaAgente {
  trocas: Troca[]
  conversaId: string | null
  aguardando: boolean
  perguntar: (pergunta: string, contexto: ContextoPergunta) => void
  novaConversa: () => void
}

/**
 * A conversa da sessão com o agente. Fica no layout, que não desmonta ao trocar de
 * tela: o painel fecha e abre sem perder as trocas.
 */
export function useConversaAgente(): ConversaAgente {
  const [trocas, setTrocas] = useState<Troca[]>([])
  const [conversaId, setConversaId] = useState<string | null>(null)
  const proximoId = useRef(0)
  const mutacao = useMutation({
    mutationFn: (corpo: Pergunta) =>
      desembrulhar(api.POST('/api/v1/assistente/perguntas', { body: corpo })),
  })
  const { mutateAsync } = mutacao

  const atualizar = useCallback((id: string, mudanca: Partial<Troca>) => {
    setTrocas((atuais) =>
      atuais.map((troca) => (troca.id === id ? { ...troca, ...mudanca } : troca)),
    )
  }, [])

  const perguntar = useCallback(
    (pergunta: string, contexto: ContextoPergunta) => {
      const texto = pergunta.trim()
      if (!texto) {
        return
      }
      proximoId.current += 1
      const id = `troca-${proximoId.current}`
      setTrocas((atuais) => [
        ...atuais,
        { id, pergunta: texto, contexto, estado: 'pendente' },
      ])
      mutateAsync({ pergunta: texto, conversa_id: conversaId, contexto }).then(
        (resposta) => {
          setConversaId(resposta.conversa_id)
          atualizar(id, { estado: 'respondida', resposta })
        },
        (erro: unknown) => {
          if (erro instanceof ErroApi && erro.code === 'CONVERSA_NAO_ENCONTRADA') {
            setConversaId(null)
          }
          atualizar(id, { estado: 'falhou', erro: mensagemDeErro(erro) })
        },
      )
    },
    [atualizar, conversaId, mutateAsync],
  )

  const novaConversa = useCallback(() => {
    setTrocas([])
    setConversaId(null)
  }, [])

  return {
    trocas,
    conversaId,
    aguardando: mutacao.isPending,
    perguntar,
    novaConversa,
  }
}
