import { useState, type FormEvent } from 'react'
import { Dialogo } from '@/components/Dialogo'
import {
  hojeLocal,
  INSPETORES,
  ROTULOS,
  validarFormulario,
  type AcaoOrdem,
  type Valores,
} from './ordens'

export function FormularioAcaoOrdem({
  acao,
  enviando,
  erro,
  aoFechar,
  aoEnviar,
  focoAoFechar,
}: {
  acao: AcaoOrdem
  enviando: boolean
  erro: string | null
  aoFechar: () => void
  aoEnviar: (valores: Valores) => void
  focoAoFechar?: () => HTMLElement | null
}) {
  const [valores, setValores] = useState<Valores>({
    inspetor: '',
    observacao: '',
    motivo: '',
    resultado: '',
    tipo_irregularidade: '',
    kwh_recuperado: '',
    data: hojeLocal(),
  })
  const [erros, setErros] = useState<Record<string, string>>({})
  const mudar = (campo: keyof Valores, valor: string) =>
    setValores((atual) => ({ ...atual, [campo]: valor }))
  function enviar(evento: FormEvent) {
    evento.preventDefault()
    const novos = validarFormulario(acao, valores)
    setErros(novos)
    if (!Object.keys(novos).length) aoEnviar(valores)
  }
  const campoTexto = (
    nome: 'observacao' | 'motivo' | 'tipo_irregularidade',
    rotulo: string,
  ) => (
    <label>
      {rotulo}
      <textarea
        value={valores[nome]}
        maxLength={2000}
        onChange={(evento) => mudar(nome, evento.target.value)}
        aria-invalid={!!erros[nome]}
      />
      {erros[nome] && <span role="alert">{erros[nome]}</span>}
    </label>
  )
  return (
    <Dialogo
      aberto
      titulo={ROTULOS[acao]}
      aoFechar={aoFechar}
      bloqueado={enviando}
      focoAoFechar={focoAoFechar}
    >
      <form className="ve-dialog-form" onSubmit={enviar} noValidate>
        {acao === 'despachar' && (
          <label>
            Inspetor
            <select
              value={valores.inspetor}
              onChange={(evento) => mudar('inspetor', evento.target.value)}
            >
              <option value="">Selecione</option>
              {INSPETORES.map((inspetor) => (
                <option key={inspetor}>{inspetor}</option>
              ))}
            </select>
            {erros.inspetor && <span role="alert">{erros.inspetor}</span>}
          </label>
        )}
        {acao === 'tentativas' && campoTexto('observacao', 'Observação')}
        {acao === 'cancelar' && campoTexto('motivo', 'Motivo do cancelamento')}
        {acao === 'resultado' && (
          <>
            <fieldset>
              <legend>Resultado</legend>
              {['IRREGULARIDADE CONFIRMADA', 'SEM IRREGULARIDADE'].map(
                (resultado) => (
                  <label key={resultado}>
                    <input
                      type="radio"
                      name="resultado"
                      value={resultado}
                      checked={valores.resultado === resultado}
                      onChange={(evento) =>
                        mudar('resultado', evento.target.value)
                      }
                    />{' '}
                    {resultado === 'SEM IRREGULARIDADE'
                      ? 'Sem irregularidade'
                      : 'Irregularidade confirmada'}
                  </label>
                ),
              )}
              {erros.resultado && <span role="alert">{erros.resultado}</span>}
            </fieldset>
            {valores.resultado === 'IRREGULARIDADE CONFIRMADA' && (
              <>
                {campoTexto('tipo_irregularidade', 'Tipo de irregularidade')}
                <label>
                  kWh recuperado
                  <input
                    inputMode="decimal"
                    value={valores.kwh_recuperado}
                    onChange={(evento) =>
                      mudar('kwh_recuperado', evento.target.value)
                    }
                  />
                  {erros.kwh_recuperado && (
                    <span role="alert">{erros.kwh_recuperado}</span>
                  )}
                </label>
              </>
            )}
            <label>
              Data da inspeção
              <input
                type="date"
                max={hojeLocal()}
                value={valores.data}
                onChange={(evento) => mudar('data', evento.target.value)}
              />
              {erros.data && <span role="alert">{erros.data}</span>}
            </label>
          </>
        )}
        {erro && <div role="alert">{erro}</div>}
        <div className="ve-row">
          <button
            className="ve-btn"
            type="button"
            disabled={enviando}
            onClick={aoFechar}
          >
            Voltar
          </button>
          <button
            className="ve-btn ve-btn-primary"
            disabled={enviando}
            type="submit"
          >
            {ROTULOS[acao]}
          </button>
        </div>
      </form>
    </Dialogo>
  )
}
