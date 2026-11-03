
import { useState } from 'react'
import {
  AlertCircle,
  ChevronDown,
  ChevronUp,
  Copy,
} from 'lucide-react'
import { Button } from '@/components/ui/button'

export type ConsumoMensal = {
  competencia: string
  consumoKwh: number | null
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
  responsavel?: string
  descricao: string
}

export type ChamadoUC = {
  id: string
  titulo: string
  protocolo: string
  abertura: string
  canal?: string
  status: string
  avaliacao: string | null
  historico: EventoChamado[]
}

export type InspecaoUC = {
  id: string
  data: string
  resultado: string
  observacao: string
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
      item.consumoKwh ?? 0,
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
              item.consumoKwh === null ? 'Sem leitura registrada' : `${item.consumoKwh} kWh`,
              item.estimado ? 'Leitura feita sem acesso ao medidor, com consumo estimado pela distribuidora' : '',
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
                  height: `${((item.consumoKwh ?? 0) / maiorConsumo) * 100}%`,
                }}
              />
            </div>
            <span className="min-h-4 text-center text-xs">
              {item.estimado && '\u25cf'}
              {item.trocaMedidor && '\u25c6'}
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
            <td className="px-3 py-3">{item.consumoKwh === null ? '—' : `${item.consumoKwh} kWh`}</td>
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

export function ExplicacaoConta({
  texto,
  efeitos,
  semCartao = false,
}: {
  texto: string | null
  efeitos?: {
    consumo: number | string
    tarifa: number | string
    bandeira: number | string
    outros: number | string
  } | null
  semCartao?: boolean
}) {
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

  const conteudo = (
    <div className="space-y-4">
      {texto ? (
        <>
          <p className="text-sm leading-7">{texto}</p>
          {efeitos && (
            <dl className="grid grid-cols-2 gap-3">
              {([
                ['Consumo', efeitos.consumo],
                ['Tarifa', efeitos.tarifa],
                ['Bandeira', efeitos.bandeira],
                ['Outros', efeitos.outros],
              ] as const).map(([rotulo, valor]) => (
                <div key={rotulo} className="rounded-md border p-3">
                  <dt className="text-xs text-muted-foreground">{rotulo}</dt>
                  <dd className="mt-1 font-semibold">
                    {Number(valor).toLocaleString('pt-BR', {
                      style: 'currency',
                      currency: 'BRL',
                    })}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <Button type="button" variant="outline" onClick={copiar}>
            <Copy className="size-4" />
            {copiado ? 'Frase copiada' : 'Copiar frase'}
          </Button>
        </>
      ) : (
        <SemDados mensagem="A explica\u00e7\u00e3o da conta ainda n\u00e3o est\u00e1 dispon\u00edvel." />
      )}
    </div>
  )

  if (semCartao) return conteudo

  return (
    <Cartao
      titulo="Por que a conta mudou"
      subtitulo="Explica\u00e7\u00e3o da \u00faltima fatura em compara\u00e7\u00e3o ao ano anterior"
    >
      {conteudo}
    </Cartao>
  )
}

export function Faturas({
  dados,
  semCartao = false,
}: {
  dados: FaturaUC[]
  semCartao?: boolean
}) {
  const conteudo = (
    <div className="space-y-4">
      {dados.length === 0 ? (
        <SemDados mensagem="Nenhuma fatura em aberto." />
      ) : (
        <Tabela colunas={['Competência', 'Vencimento', 'Valor', 'Atraso']}>
          {dados.map((fatura) => (
            <tr key={fatura.id}>
              <td className="px-3 py-3">{fatura.competencia}</td>
              <td className="px-3 py-3">{fatura.vencimento}</td>
              <td className="px-3 py-3">{formatarMoeda(fatura.valor)}</td>
              <td className="px-3 py-3">
                {fatura.diasAtraso == null || fatura.diasAtraso <= 0
                  ? 'Em dia'
                  : `${fatura.diasAtraso} dias`}
              </td>
            </tr>
          ))}
        </Tabela>
      )}
    </div>
  )

  if (semCartao) return conteudo

  return (
    <Cartao
      titulo="Faturas em aberto"
      subtitulo={`${dados.length} fatura(s) em aberto`}
    >
      {conteudo}
    </Cartao>
  )
}

export function Interrupcoes({
  dados,
  semCartao = false,
}: {
  dados: InterrupcaoUC[]
  semCartao?: boolean
}) {
  const conteudo = (
    <div className="space-y-4">
      {dados.length === 0 ? (
        <SemDados mensagem="Nenhuma interrupção registrada." />
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
    </div>
  )

  if (semCartao) return conteudo

  return (
    <Cartao
      titulo="Interrupções"
      subtitulo="Histórico de interrupções da unidade consumidora"
    >
      {conteudo}
    </Cartao>
  )
}

export function Chamados({ dados, semCartao = false }: { dados: ChamadoUC[]; semCartao?: boolean }) {
  const [expandidos, setExpandidos] = useState<string[]>([])

  function alternar(id: string) {
    setExpandidos((anteriores) =>
      anteriores.includes(id)
        ? anteriores.filter((atual) => atual !== id)
        : [...anteriores, id],
    )
  }

  const conteudo = (
    <div className="space-y-4">

      {dados.length === 0 ? (
        <SemDados mensagem="Histórico de atendimentos ainda não disponível." />
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
                      Protocolo {chamado.protocolo} · {chamado.abertura}{chamado.canal ? ` · ${chamado.canal}` : ''}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {chamado.status}
                      {chamado.avaliacao !== null
                        ? ` · Avaliação ${Number(chamado.avaliacao).toLocaleString("pt-BR", { maximumFractionDigits: 1 })}/5`
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
                            {evento.data}{evento.responsavel ? ` · ${evento.responsavel}` : ''}
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
    </div>
  )

  if (semCartao) return conteudo

  return (
    <Cartao
      titulo="Atendimentos"
      subtitulo={`${dados.length} atendimento(s) · histórico de atendimento`}
    >
      {conteudo}
    </Cartao>
  )
}

export function Inspecoes({
  semCartao = false,
  dados,
  ordemAtiva,
  motivoSuspeita,
}: {
  semCartao?: boolean
  dados: InspecaoUC[]
  ordemAtiva: string | null
  motivoSuspeita: string | null
}) {
  const conteudo = (
    <div className="space-y-4">
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
    </div>
  )

  if (semCartao) return conteudo

  return (
    <Cartao titulo="Inspeções" subtitulo="Histórico de inspeções e ordens">
      {conteudo}
    </Cartao>
  )
}
