import { useId } from 'react'
import { ChevronDown } from 'lucide-react'

export interface OpcaoSelecao {
  valor: string
  rotulo: string
}

export interface SelecaoProps {
  id?: string
  rotulo: string
  valor: string
  aoMudar: (novoValor: string) => void
  opcoes: ReadonlyArray<string | OpcaoSelecao>
  placeholder?: string
  desabilitado?: boolean
  carregando?: boolean
}

export function Selecao({
  id,
  rotulo,
  valor,
  aoMudar,
  opcoes,
  placeholder = 'Todos',
  desabilitado = false,
  carregando = false,
}: SelecaoProps) {
  const idGerado = useId()
  const idSelect = id ?? idGerado
  const ativo = valor.trim().length > 0

  return (
    <div className={`ve-select ${ativo ? 've-select-active' : ''}`.trim()}>
      <label htmlFor={idSelect} className="ve-select-label">
        {rotulo}
      </label>
      <div className="ve-select-box">
        <select
          id={idSelect}
          aria-label={rotulo}
          value={valor}
          disabled={desabilitado || carregando}
          onChange={(e) => aoMudar(e.target.value)}
        >
          <option value="">
            {carregando ? 'Carregando...' : placeholder}
          </option>
          {opcoes.map((op) => {
            const item =
              typeof op === 'string' ? { valor: op, rotulo: op } : op
            return (
              <option key={item.valor} value={item.valor}>
                {item.rotulo}
              </option>
            )
          })}
        </select>
        <ChevronDown size={14} className="ve-icon" aria-hidden="true" />
      </div>
    </div>
  )
}
