import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { EstadoIndisponivel } from '@/components/Estados'
import { Etiqueta } from '@/components/Etiqueta'
import { Painel } from '@/components/Painel'
import { normalizarUc } from '@/features/unidade-consumidora/normalizarUc'

export function PaginaUnidadeConsumidora() {
  const [searchParams, setSearchParams] = useSearchParams()
  const ucParametro = searchParams.get('uc') ?? ''
  const ucNormalizadaUrl = normalizarUc(ucParametro)

  const [entrada, setEntrada] = useState<string>(
    ucNormalizadaUrl ?? ucParametro,
  )
  const [erroValidacao, setErroValidacao] = useState<string | null>(null)

  const aoSubmeterBusca = (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const normalizada = normalizarUc(entrada)
    if (!normalizada) {
      setErroValidacao(
        'Informe uma UC válida com 6 dígitos (ex.: UC100123 ou 100123).',
      )
      return
    }
    setErroValidacao(null)
    setEntrada(normalizada)
    const proximo = new URLSearchParams(searchParams)
    proximo.set('uc', normalizada)
    setSearchParams(proximo)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <header
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'flex-end',
          justifyContent: 'space-between',
          gap: '16px',
        }}
      >
        <div>
          <h1
            style={{
              margin: 0,
              fontSize: '26px',
              lineHeight: '32px',
              fontWeight: 600,
              letterSpacing: '-0.01em',
            }}
          >
            Unidade Consumidora
          </h1>
          <p
            style={{
              margin: '4px 0 0',
              fontSize: '13px',
              lineHeight: '18px',
              color: 'var(--ink-muted)',
            }}
          >
            Esta tela ignora o período global e mostra sempre os últimos 12
            meses da UC.
          </p>
        </div>

        <form
          onSubmit={aoSubmeterBusca}
          className={`ve-ucsearch ${erroValidacao ? 've-ucsearch-error' : ''}`.trim()}
          style={{ minWidth: '320px' }}
          noValidate
        >
          <label htmlFor="campo-numero-uc" className="ve-select-label">
            Número da UC
          </label>
          <div className="ve-ucsearch-box">
            <div className="ve-ucsearch-field">
              <Search size={15} className="ve-icon" aria-hidden="true" />
              <input
                id="campo-numero-uc"
                type="text"
                value={entrada}
                onChange={(e) => {
                  setEntrada(e.target.value)
                  if (erroValidacao) {
                    setErroValidacao(null)
                  }
                }}
                placeholder="UC100123"
              />
            </div>
            <button type="submit" className="ve-btn ve-btn-primary">
              Buscar
            </button>
          </div>
          <span
            className="ve-ucsearch-hint"
            role={erroValidacao ? 'alert' : undefined}
          >
            {erroValidacao ?? 'Aceita UC100123, uc100123 ou 100123.'}
          </span>
        </form>
      </header>

      <Painel
        titulo={
          <span className="ve-row" style={{ gap: 'var(--space-2)' }}>
            <span>Cadastro da UC</span>
            {ucNormalizadaUrl && (
              <span className="ve-mono" style={{ fontSize: '14px' }}>
                {ucNormalizadaUrl}
              </span>
            )}
          </span>
        }
        subtitulo="Dados cadastrais, classe, alimentador, medidor e geração distribuída"
        acoes={<Etiqueta>Últimos 12 meses da UC</Etiqueta>}
      >
        <EstadoIndisponivel compacto />
      </Painel>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.45fr) minmax(0, 1fr)',
          gap: '24px',
          alignItems: 'stretch',
        }}
      >
        <Painel
          titulo="Consumo — últimos 12 meses"
          subtitulo="kWh por competência · cinza = mesmos meses do ano anterior"
          preencher
        >
          <EstadoIndisponivel compacto />
        </Painel>

        <Painel
          titulo="Por que a conta mudou"
          subtitulo="Última fatura × mesmo mês do ano anterior"
          preencher
        >
          <EstadoIndisponivel compacto />
        </Painel>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(2, minmax(0, 1fr))',
          gap: '24px',
          alignItems: 'stretch',
        }}
      >
        <Painel
          titulo="Faturas em aberto"
          subtitulo="Competência, vencimento, valor e atraso"
          preencher
        >
          <EstadoIndisponivel compacto />
        </Painel>

        <Painel
          titulo="Interrupções — últimos 12 meses"
          subtitulo="Da UC e do alimentador no mesmo período"
          preencher
        >
          <EstadoIndisponivel compacto />
        </Painel>
      </div>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'minmax(0, 1.25fr) minmax(0, 1fr)',
          gap: '24px',
          alignItems: 'stretch',
        }}
      >
        <Painel
          titulo="Chamados"
          subtitulo="Últimos 12 meses · mais recente primeiro"
          preencher
        >
          <EstadoIndisponivel compacto />
        </Painel>

        <Painel
          titulo="Inspeções"
          subtitulo="Históricas e ordem de inspeção ativa"
          preencher
        >
          <EstadoIndisponivel compacto />
        </Painel>
      </div>
    </div>
  )
}
