
import { useState } from 'react'
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Copy,
  FileText,
  Zap,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export type ConsumoMensal = {
  competencia: string
  consumoKwh: number
  consumoAnoAnteriorKwh: number | null
  estimado: boolean
  trocaMedidor: boolean
}

export type FaturaUC = {
  id: string
  competencia: string
  vencimento: string
  valor: number
  diasAtraso: number
}

export type InterrupcaoUC = {
  id: string
  data: string
  duracao: string
  causa: string
}

export type EventoChamado = {
  id: string
  data: string
  responsavel: string
  descricao: string
}

export type ChamadoUC = {
  id: string
  titulo: string
  protocolo: string
  abertura: string
  canal: string
  status: string
  avaliacao: number | null
  historico: EventoChamado[]
}

export type InspecaoUC = {
  id: string
  data: string
  resultado: string
  observacao: string
}

export type DadosUnidadeConsumidora = {
  identificador: string
  titular: string
  documentoMascarado: string
  classe: string
  endereco: string
  alimentador: string
  medidor: string
  situacao: string
  geracaoDistribuida: string | null
  consumo: ConsumoMensal[]
  faturas: FaturaUC[]
  interrupcoes: InterrupcaoUC[]
  chamados: ChamadoUC[]
  inspecoes: InspecaoUC[]
  ordemAtiva: string | null
  motivoSuspeita: string | null
  explicacaoConta: string | null
}

function formatarMoeda(valor: number) {
  return new Intl.NumberFormat('pt-BR', {
    style: 'currency',
    currency: 'BRL',
  }).format(valor)
}

function Cartao({
  titulo,
  subtitulo,
  children,
}: {
  titulo: string
  subtitulo?: string
  children: React.ReactNode
}) {
  return (
    <section className="min-w-0 rounded-lg border bg-card p-5">
      <div className="mb-5">
        <h3 className="text-base font-semibold">{titulo}</h3>
        {subtitulo && (
          <p className="mt-1 text-sm text-muted-foreground">
            {subtitulo}
          </p>
        )}
      </div>
      {children}
    </section>
  )
}

function SemDados({ mensagem }: { mensagem: string }) {
  return (
    <p className="rounded-md border border-dashed p-5 text-center text-sm text-muted-foreground">
      {mensagem}
    </p>
  )
}

function Tabela({
  colunas,
  children,
}: {
  colunas: string[]
  children: React.ReactNode
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="border-b text-muted-foreground">
          <tr>
            {colunas.map((coluna) => (
              <th key={coluna} className="whitespace-nowrap px-3 py-3 font-medium">
                {coluna}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">{children}</tbody>
      </table>
    </div>
  )
}

export function GraficoConsumo({ dados }: { dados: ConsumoMensal[] }) {
  if (dados.length === 0) {
    return <SemDados mensagem="Histórico de consumo ainda não disponível." />
  }

  const maiorConsumo = Math.max(
    1,
    ...dados.flatMap((item) => [
      item.consumoKwh,
      item.consumoAnoAnteriorKwh ?? 0,
    ]),
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span><span className="mr-2 inline-block size-2 rounded-sm bg-foreground" />Últimos 12 meses</span>
        <span><span className="mr-2 inline-block size-2 rounded-sm bg-gray-300" />Ano anterior</span>
        <span>● Leitura estimada</span>
        <span>◆ Troca de medidor</span>
      </div>

      <div
        className="flex h-56 items-end gap-2 overflow-x-auto border-b pb-2"
        role="img"
        aria-label="Gráfico de consumo mensal comparado ao ano anterior"
      >
        {dados.map((item) => (
          <div
            key={item.competencia}
            className="flex h-full min-w-12 flex-1 flex-col justify-end gap-1"
            title={[
              item.competencia,
              `${item.consumoKwh} kWh`,
              item.estimado ? 'consumo estimado pela média da UC' : '',
              item.trocaMedidor ? 'Troca de medidor' : '',
            ].filter(Boolean).join(' · ')}
          >
            <div className="flex h-44 items-end justify-center gap-1">
              <div
                className="w-3 rounded-t-sm bg-gray-300"
                style={{
                  height: `${((item.consumoAnoAnteriorKwh ?? 0) / maiorConsumo) * 100}%`,
                }}
              />
              <div
                className="w-3 rounded-t-sm bg-foreground"
                style={{
                  height: `${(item.consumoKwh / maiorConsumo) * 100}%`,
                }}
              />
            </div>
            <span className="min-h-4 text-center text-xs">
              {item.estimado ? '●' : item.trocaMedidor ? '◆' : ''}
            </span>
            <span className="text-center text-[11px] text-muted-foreground">
              {item.competencia}
            </span>
          </div>
        ))}
      </div>

      <Tabela colunas={['Competência', 'Consumo', 'Ano anterior', 'Observação']}>
        {dados.map((item) => (
          <tr key={item.competencia}>
            <td className="px-3 py-3">{item.competencia}</td>
            <td className="px-3 py-3">{item.consumoKwh} kWh</td>
            <td className="px-3 py-3">
              {item.consumoAnoAnteriorKwh === null
                ? '—'
                : `${item.consumoAnoAnteriorKwh} kWh`}
            </td>
            <td className="px-3 py-3 text-muted-foreground">
              {[
                item.estimado ? 'Leitura estimada' : '',
                item.trocaMedidor ? 'Troca de medidor' : '',
              ].filter(Boolean).join(' · ') || '—'}
            </td>
          </tr>
        ))}
      </Tabela>
    </div>
  )
}

function ExplicacaoConta({ texto }: { texto: string | null }) {
  const [copiado, setCopiado] = useState(false)

  async function copiar() {
    if (!texto) return

    try {
      await navigator.clipboard.writeText(texto)
      setCopiado(true)
    } catch {
      setCopiado(false)
    }
  }

  return (
    <Cartao
      titulo="Por que a conta mudou"
      subtitulo="Explicação da última fatura em comparação ao ano anterior"
    >
      {texto ? (
        <div className="space-y-4">
          <p className="text-sm leading-7">{texto}</p>
          <Button type="button" variant="outline" onClick={copiar}>
            <Copy className="size-4" />
            {copiado ? 'Frase copiada' : 'Copiar frase'}
          </Button>
        </div>
      ) : (
        <SemDados mensagem="A explicação da conta ainda não está disponível." />
      )}
    </Cartao>
  )
}

function Faturas({ dados }: { dados: FaturaUC[] }) {
  return (
    <Cartao
      titulo="Faturas em aberto"
      subtitulo={`${dados.length} fatura(s) em aberto`}
    >
      {dados.length === 0 ? (
        <SemDados mensagem="Informações de faturas ainda não disponíveis." />
      ) : (
        <Tabela colunas={['Competência', 'Vencimento', 'Valor', 'Atraso']}>
          {dados.map((fatura) => (
            <tr key={fatura.id}>
              <td className="px-3 py-3">{fatura.competencia}</td>
              <td className="px-3 py-3">{fatura.vencimento}</td>
              <td className="px-3 py-3">{formatarMoeda(fatura.valor)}</td>
              <td className="px-3 py-3">{fatura.diasAtraso} dias</td>
            </tr>
          ))}
        </Tabela>
      )}
    </Cartao>
  )
}

function Interrupcoes({ dados }: { dados: InterrupcaoUC[] }) {
  return (
    <Cartao
      titulo="Interrupções — últimos 12 meses"
      subtitulo="Histórico de interrupções da unidade consumidora"
    >
      {dados.length === 0 ? (
        <SemDados mensagem="Histórico de interrupções ainda não disponível." />
      ) : (
        <Tabela colunas={['Data', 'Duração', 'Causa']}>
          {dados.map((interrupcao) => (
            <tr key={interrupcao.id}>
              <td className="px-3 py-3">{interrupcao.data}</td>
              <td className="px-3 py-3">{interrupcao.duracao}</td>
              <td className="px-3 py-3">{interrupcao.causa}</td>
            </tr>
          ))}
        </Tabela>
      )}
    </Cartao>
  )
}

function Chamados({ dados }: { dados: ChamadoUC[] }) {
  const [expandidos, setExpandidos] = useState<string[]>([])

  function alternar(id: string) {
    setExpandidos((anteriores) =>
      anteriores.includes(id)
        ? anteriores.filter((atual) => atual !== id)
        : [...anteriores, id],
    )
  }

  return (
    <Cartao
      titulo="Chamados"
      subtitulo={`${dados.length} chamado(s) · histórico de atendimento`}
    >
      {dados.length === 0 ? (
        <SemDados mensagem="Histórico de chamados ainda não disponível." />
      ) : (
        <div className="space-y-3">
          {dados.map((chamado) => {
            const aberto = expandidos.includes(chamado.id)

            return (
              <div key={chamado.id} className="rounded-md border">
                <button
                  type="button"
                  aria-expanded={aberto}
                  onClick={() => alternar(chamado.id)}
                  className="flex w-full items-start justify-between gap-3 p-4 text-left"
                >
                  <span className="space-y-1">
                    <span className="block font-medium">{chamado.titulo}</span>
                    <span className="block text-xs text-muted-foreground">
                      Protocolo {chamado.protocolo} · {chamado.abertura} · {chamado.canal}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {chamado.status}
                      {chamado.avaliacao !== null
                        ? ` · Avaliação ${chamado.avaliacao}/5`
                        : ''}
                    </span>
                  </span>
                  {aberto ? (
                    <ChevronUp className="size-4 shrink-0" />
                  ) : (
                    <ChevronDown className="size-4 shrink-0" />
                  )}
                </button>

                {aberto && (
                  <div className="space-y-4 border-t p-4">
                    {chamado.historico.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Nenhum evento registrado.
                      </p>
                    ) : (
                      chamado.historico.map((evento) => (
                        <div key={evento.id} className="border-l-2 pl-3">
                          <p className="text-xs font-medium">
                            {evento.data} · {evento.responsavel}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {evento.descricao}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </Cartao>
  )
}

function Inspecoes({
  dados,
  ordemAtiva,
  motivoSuspeita,
}: {
  dados: InspecaoUC[]
  ordemAtiva: string | null
  motivoSuspeita: string | null
}) {
  return (
    <Cartao titulo="Inspeções" subtitulo="Histórico de inspeções e ordens">
      {ordemAtiva && (
        <div role="status" className="mb-4 rounded-md border p-3 text-sm">
          <p className="flex items-center gap-2 font-medium">
            <AlertCircle className="size-4" />
            Ordem ativa: {ordemAtiva}
          </p>
          {motivoSuspeita && (
            <p className="mt-2 text-muted-foreground">{motivoSuspeita}</p>
          )}
        </div>
      )}

      {dados.length === 0 ? (
        <SemDados mensagem="Informações de inspeções ainda não disponíveis." />
      ) : (
        <Tabela colunas={['Data', 'Resultado', 'Observação']}>
          {dados.map((inspecao) => (
            <tr key={inspecao.id}>
              <td className="px-3 py-3">{inspecao.data}</td>
              <td className="px-3 py-3">{inspecao.resultado}</td>
              <td className="px-3 py-3">{inspecao.observacao}</td>
            </tr>
          ))}
        </Tabela>
      )}
    </Cartao>
  )
}

export function SecoesUnidadeConsumidora({
  dados,
}: {
  dados: DadosUnidadeConsumidora
}) {
  const identificacao = [
    ['CPF/CNPJ', dados.documentoMascarado],
    ['Classe', dados.classe],
    ['Endereço', dados.endereco],
    ['Alimentador', dados.alimentador],
    ['Medidor atual', dados.medidor],
  ]

  return (
    <div className="space-y-6">
      <section className="rounded-lg border bg-card p-5">
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="text-xl font-semibold">{dados.identificador}</h2>
          <span className="rounded-md bg-secondary px-2 py-1 text-xs">
            {dados.situacao}
          </span>
          {dados.geracaoDistribuida && (
            <span className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs">
              <Zap className="size-3" />
              {dados.geracaoDistribuida}
            </span>
          )}
        </div>

        <p className="mt-2 font-medium">{dados.titular}</p>

        <dl className="mt-5 grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          {identificacao.map(([rotulo, valor]) => (
            <div key={rotulo}>
              <dt className="text-xs text-muted-foreground">{rotulo}</dt>
              <dd className="mt-1 text-sm font-medium">{valor}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(320px,1fr)]">
        <Cartao
          titulo="Consumo — últimos 12 meses"
          subtitulo="kWh por competência · comparação com o mesmo mês do ano anterior"
        >
          <GraficoConsumo dados={dados.consumo} />
        </Cartao>

        <ExplicacaoConta texto={dados.explicacaoConta} />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Faturas dados={dados.faturas} />
        <Interrupcoes dados={dados.interrupcoes} />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Chamados dados={dados.chamados} />
        <Inspecoes
          dados={dados.inspecoes}
          ordemAtiva={dados.ordemAtiva}
          motivoSuspeita={dados.motivoSuspeita}
        />
      </div>

      <p className="flex items-center gap-2 text-xs text-muted-foreground">
        <FileText className="size-4" />
        Dados da unidade consumidora
        <ClipboardList className="size-4" />
        Histórico operacional
      </p>
    </div>
  )
}
