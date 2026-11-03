import { useEffect, useState } from 'react'
import { AlertTriangle, CircleHelp } from 'lucide-react'
import { Etiqueta } from '@/components/Etiqueta'
import type { RespostaPergunta } from '@/features/assistente/conversa'

const ETAPAS = ['Entendendo a pergunta', 'Consultando os dados', 'Redigindo'] as const
// A resposta chega inteira (sem streaming): as etapas acompanham o tempo típico de cada passo.
const INICIO_ETAPA_MS = [0, 1500, 4000]

export function EtapasEspera() {
  const [etapa, setEtapa] = useState(0)

  useEffect(() => {
    const timers = INICIO_ETAPA_MS.slice(1).map((inicio, indice) =>
      setTimeout(() => setEtapa(indice + 1), inicio),
    )
    return () => timers.forEach(clearTimeout)
  }, [])

  return (
    <ol className="ve-agent-steps" role="status" aria-label="Andamento da resposta">
      {ETAPAS.map((rotulo, indice) => (
        <li
          key={rotulo}
          data-estado={indice < etapa ? 'feita' : indice === etapa ? 'atual' : 'proxima'}
          aria-current={indice === etapa ? 'step' : undefined}
        >
          {rotulo}
        </li>
      ))}
    </ol>
  )
}

export interface RespostaAgenteProps {
  resposta: RespostaPergunta
  aoPerguntar: (pergunta: string) => void
}

export function RespostaAgente({ resposta, aoPerguntar }: RespostaAgenteProps) {
  if (resposta.tipo === 'nao_sei') {
    return (
      <div className="ve-agent-nao-sei" role="status">
        <div className="ve-agent-nao-sei-title">
          <CircleHelp size={16} className="ve-icon" aria-hidden="true" />
          <strong>Não sei responder com os dados disponíveis</strong>
        </div>
        {resposta.motivo && <p>{resposta.motivo}</p>}
        {resposta.alternativa && (
          <div className="ve-agent-alternativa">
            <span className="ve-muted">Os dados respondem, por exemplo:</span>
            <button
              type="button"
              className="ve-btn ve-btn-sm"
              onClick={() => aoPerguntar(resposta.alternativa ?? '')}
            >
              {resposta.alternativa}
            </button>
          </div>
        )}
        <Chips resposta={resposta} />
        {(resposta.consultas ?? []).length > 0 && <ComoCheguei resposta={resposta} />}
      </div>
    )
  }

  return (
    <div className="ve-agent-answer">
      <p>{resposta.texto}</p>
      <Chips resposta={resposta} />
      <ComoCheguei resposta={resposta} />
    </div>
  )
}

function Chips({ resposta }: { resposta: RespostaPergunta }) {
  const filtros = resposta.filtros ?? []
  if (!resposta.periodo && !resposta.metrica && filtros.length === 0) {
    return null
  }
  return (
    <div className="ve-agent-chips" aria-label="Período, métrica e filtros usados">
      {resposta.periodo && (
        <Etiqueta variante="marca">Período: {resposta.periodo.descricao}</Etiqueta>
      )}
      {resposta.metrica && <Etiqueta>Métrica: {resposta.metrica}</Etiqueta>}
      {filtros.map((filtro) => (
        <Etiqueta key={filtro}>{filtro}</Etiqueta>
      ))}
    </div>
  )
}

function ComoCheguei({ resposta }: { resposta: RespostaPergunta }) {
  const consultas = resposta.consultas ?? []
  const ultima = consultas.at(-1)
  const anteriores = consultas.slice(0, -1)
  const colunas = ultima?.colunas ?? []
  const linhas = ultima?.linhas ?? []

  return (
    <details className="ve-agent-how">
      <summary>Como cheguei a esta resposta</summary>
      {anteriores.map((tentativa, indice) => (
        <div key={indice} className="ve-agent-tentativa">
          <AlertTriangle size={14} className="ve-icon" aria-hidden="true" />
          <span>
            Tentativa {indice + 1} corrigida: {tentativa.erro ?? 'sem resultado'}
          </span>
        </div>
      ))}
      {ultima?.sql_executado ? (
        <>
          <p className="ve-agent-how-label">SQL executado (somente leitura)</p>
          <pre className="ve-agent-sql">
            <code>{ultima.sql_executado}</code>
          </pre>
        </>
      ) : (
        ultima && (
          <p className="ve-muted">Nenhuma consulta foi executada: {ultima.erro}</p>
        )
      )}
      {ultima?.erro && ultima.sql_executado && (
        <p className="ve-muted">A consulta falhou: {ultima.erro}</p>
      )}
      {colunas.length > 0 && (
        <div className="ve-table-root">
          <div className="ve-table-wrap">
            <table className="ve-table">
              <caption className="ve-sr">Resultado da consulta</caption>
              <thead>
                <tr>
                  {colunas.map((coluna) => (
                    <th key={coluna} scope="col">
                      {coluna}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {linhas.map((linha, indice) => (
                  <tr key={indice}>
                    {linha.map((valor, coluna) => (
                      <td key={coluna} className={typeof valor === 'number' ? 've-right ve-num' : ''}>
                        {formatarCelula(valor)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="ve-table-foot">{rotuloLinhas(ultima?.total_linhas ?? 0, linhas.length)}</div>
        </div>
      )}
      <p className="ve-agent-meta">
        Modelo {resposta.modelo} · {resposta.latencia_ms.toLocaleString('pt-BR')} ms ·{' '}
        {(resposta.tokens_entrada + resposta.tokens_saida).toLocaleString('pt-BR')} tokens ·
        auditoria <span className="ve-mono">{resposta.id_resposta.slice(0, 8)}</span>
      </p>
    </details>
  )
}

function formatarCelula(valor: unknown): string {
  if (valor === null || valor === undefined) {
    return '—'
  }
  if (typeof valor === 'number') {
    return valor.toLocaleString('pt-BR', { maximumFractionDigits: 4 })
  }
  return String(valor)
}

function rotuloLinhas(total: number, mostradas: number): string {
  const linhas = `${total.toLocaleString('pt-BR')} ${total === 1 ? 'linha' : 'linhas'}`
  return mostradas < total ? `${linhas}, mostradas as ${mostradas} primeiras` : linhas
}
