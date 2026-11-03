import { useState, type FormEvent } from 'react'
import { Search } from 'lucide-react'
import { useNavigate, useParams, useSearchParams } from 'react-router'
import { EstadoIndisponivel } from '@/components/Estados'
import { Etiqueta } from '@/components/Etiqueta'
import { Painel } from '@/components/Painel'
import { adaptarConsumoUC } from '@/features/unidade-consumidora/adaptarConsumoUC'
import { mascararDocumento } from '@/features/unidade-consumidora/mascararDocumento'
import { Chamados, ExplicacaoConta, Faturas, GraficoConsumo, Inspecoes, Interrupcoes } from '@/features/unidade-consumidora/SecoesUnidadeConsumidora'
import { normalizarUc } from '@/features/unidade-consumidora/normalizarUc'
import { useUnidadeConsumidora } from '@/features/unidade-consumidora/useUnidadeConsumidora'

export function PaginaUnidadeConsumidora() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const ucParametro = id ?? searchParams.get('uc') ?? ''

  return <ConteudoUnidadeConsumidora key={ucParametro} ucParametro={ucParametro} rotaComId={id !== undefined} />
}

function ConteudoUnidadeConsumidora({ ucParametro, rotaComId }: { ucParametro: string; rotaComId: boolean }) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const ucNormalizadaUrl = normalizarUc(ucParametro)
  const consultaUC = useUnidadeConsumidora(ucNormalizadaUrl)

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
    if (rotaComId) {
      navigate(`/ucs/${normalizada}`)
      return
    }

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
        {!ucNormalizadaUrl ? (
          <EstadoIndisponivel compacto />
        ) : consultaUC.isPending ? (
          <p role="status">Carregando dados da unidade consumidora...</p>
        ) : consultaUC.isError ? (
          <p role="alert">
            {consultaUC.error.status === 404
              ? 'Unidade consumidora não encontrada.'
              : 'Não foi possível carregar os dados da unidade consumidora.'}
          </p>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-3">
              <strong className="text-lg">{consultaUC.data.cabecalho.titular}</strong>
              {consultaUC.data.cabecalho.gd && (
                <Etiqueta>
                  GD {Number(consultaUC.data.cabecalho.gd.potencia_kw).toLocaleString('pt-BR')} kWp
                </Etiqueta>
              )}
            </div>
            <dl className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[
                ['CPF/CNPJ', mascararDocumento(consultaUC.data.cabecalho.documento)],
                ['Classe', consultaUC.data.cabecalho.classe],
                ['Endereço', consultaUC.data.cabecalho.endereco],
                ['Município', consultaUC.data.cabecalho.municipio],
                ['Bairro', consultaUC.data.cabecalho.bairro],
                ['Alimentador', consultaUC.data.cabecalho.alimentador],
                ['Medidor atual', consultaUC.data.cabecalho.medidor_atual?.id_medidor],
                ['Conexão GD', consultaUC.data.cabecalho.gd?.data_conexao],
              ].map(([rotulo, valor]) => (
                <div key={rotulo}>
                  <dt className="text-xs text-muted-foreground">{rotulo}</dt>
                  <dd className="mt-1 text-sm font-medium">{valor || '—'}</dd>
                </div>
              ))}
            </dl>
          </div>
        )}
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
          {consultaUC.isSuccess ? (
          <GraficoConsumo dados={adaptarConsumoUC(consultaUC.data.consumo)} />
        ) : (
          <EstadoIndisponivel compacto />
        )}
        </Painel>

        <Painel
          titulo="Por que a conta mudou"
          subtitulo="Última fatura × mesmo mês do ano anterior"
          preencher
        >
          {consultaUC.isSuccess ? (
            <ExplicacaoConta
              texto={consultaUC.data.explicacao_conta.frase}
              efeitos={consultaUC.data.explicacao_conta.efeitos}
              semCartao
            />
          ) : (
            <EstadoIndisponivel compacto />
          )}
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
          {consultaUC.isSuccess ? (
            <Faturas
              semCartao
              dados={consultaUC.data.faturas_abertas.map((fatura) => ({
                id: fatura.id_fatura,
                competencia: fatura.competencia.slice(0, 7),
                vencimento: fatura.data_vencimento,
                valor: Number(fatura.valor_total),
                diasAtraso: fatura.dias_atraso ?? 0,
              }))}
            />
          ) : (
            <EstadoIndisponivel compacto />
          )}
        </Painel>

        <Painel
          titulo="Interrupções — últimos 12 meses"
          subtitulo="Da UC e do alimentador no mesmo período"
          preencher
        >
          {consultaUC.isSuccess ? (
            <Interrupcoes
              semCartao
              dados={consultaUC.data.interrupcoes.ocorrencias.map((ocorrencia) => ({
                id: ocorrencia.id_ocorrencia,
                data: new Date(ocorrencia.data_abertura).toLocaleDateString('pt-BR'),
                duracao: `${Number(ocorrencia.duracao_efetiva_min).toLocaleString('pt-BR')} min`,
                causa: ocorrencia.causa,
              }))}
            />
          ) : (
            <EstadoIndisponivel compacto />
          )}
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
          {consultaUC.isSuccess ? (
            <Chamados
              semCartao
              dados={consultaUC.data.chamados.map((chamado) => ({
                id: chamado.protocolo,
                titulo: chamado.assunto,
                protocolo: chamado.protocolo,
                abertura: new Date(chamado.aberto_em).toLocaleDateString('pt-BR'),
                status: chamado.status,
                avaliacao: chamado.nota,
                historico: chamado.historico.map((evento) => ({
                  id: `${chamado.protocolo}-${evento.sequencia}`,
                  data: new Date(evento.data).toLocaleDateString('pt-BR'),
                  descricao: evento.descricao,
                })),
              }))}
            />
          ) : (
            <EstadoIndisponivel compacto />
          )}
        </Painel>

        <Painel
          titulo="Inspeções"
          subtitulo="Históricas e ordem de inspeção ativa"
          preencher
        >
          {consultaUC.isSuccess ? (
            <Inspecoes
              semCartao
              dados={consultaUC.data.inspecoes.map((inspecao) => ({
                id: inspecao.id_inspecao,
                data: new Date(inspecao.data).toLocaleDateString('pt-BR'),
                resultado: inspecao.resultado,
                observacao: inspecao.tipo_irregularidade ?? inspecao.origem,
              }))}
              ordemAtiva={
                consultaUC.data.ordem_ativa
                  ? `${consultaUC.data.ordem_ativa.id} (${consultaUC.data.ordem_ativa.status})`
                  : null
              }
              motivoSuspeita={
                consultaUC.data.ordem_ativa?.motivos.join(', ') ?? null
              }
            />
          ) : (
            <EstadoIndisponivel compacto />
          )}
        </Painel>
      </div>
    </div>
  )
}
