import { GraficoBarrasComparativas } from '@/components/Graficos'
import { formatarKwh, formatarMoeda, formatarNumero } from '@/lib/formatacao'

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
  diasAtraso: number | null
}

export type InterrupcaoUC = {
  id: string
  data: string
  duracao: string
  duracaoBruta?: string
  sobreposicao?: boolean
  causa: string
}

export type EtapaAtendimento = {
  id: string
  data: string
  responsavel?: string
  descricao: string
}

export type AtendimentoUC = {
  id: string
  titulo: string
  protocolo: string
  abertura: string
  canal?: string
  status: string
  avaliacao: string | null
  historico: EtapaAtendimento[]
}

export type InspecaoUC = {
  id: string
  data: string
  resultado: string
  origem: string
  tipoIrregularidade: string | null
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

  const pontos = dados.map((item) => ({
    rotulo: item.competencia,
    atual: item.consumoKwh,
    comparacao: item.consumoAnoAnteriorKwh,
  }))

  const marcadores = Object.fromEntries(
    dados
      .filter((item) => item.estimado || item.trocaMedidor)
      .map((item) => [
        item.competencia,
        `${item.estimado ? '\u25cf' : ''}${item.trocaMedidor ? '\u25c6' : ''}`,
      ]),
  )

  const observacoes = Object.fromEntries(
    dados
      .filter((item) => item.estimado || item.trocaMedidor)
      .map((item) => [
        item.competencia,
        [
          item.estimado ? 'Leitura estimada' : '',
          item.trocaMedidor ? 'Troca de medidor: consumo estimado pela mediana da UC' : '',
        ].filter(Boolean).join(' · '),
      ]),
  )

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground">
        <span><span className="mr-2 inline-block size-2 rounded-sm bg-[var(--data-2)]" />Últimos 12 meses</span>
        <span><span className="mr-2 inline-block size-2 rounded-sm bg-[var(--data-compare)]" />Ano anterior</span>
        <span>● Leitura estimada</span>
        <span>◆ Troca de medidor</span>
      </div>

      <div role="img" aria-label="Gráfico de consumo mensal comparado ao ano anterior">
        <GraficoBarrasComparativas
          dados={pontos}
          rotuloAtual="Últimos 12 meses"
          corAtual="data-2"
          rotuloComparacao="Ano anterior"
          altura={260}
          formatarValor={(valor) => formatarKwh(valor, 1)}
          observacoes={observacoes}
          marcadores={marcadores}
        />
      </div>

      <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
        {dados.filter((item) => item.estimado || item.trocaMedidor).map((item) => (
          <span key={item.competencia}>
            {item.competencia}: {[
              item.estimado ? '● Leitura estimada' : '',
              item.trocaMedidor ? '◆ Troca de medidor: consumo estimado pela mediana da UC' : '',
            ].filter(Boolean).join(' · ')}
          </span>
        ))}
      </div>
      <Tabela colunas={['Competência', 'Consumo', 'Ano anterior', 'Observação']}>
        {dados.map((item) => (
          <tr key={item.competencia}>
            <td className="px-3 py-3">{item.competencia}</td>
            <td className="px-3 py-3">{item.consumoKwh === null ? '—' : formatarKwh(item.consumoKwh, 1)}</td>
            <td className="px-3 py-3">
              {item.consumoAnoAnteriorKwh === null
                ? '—'
                : formatarKwh(item.consumoAnoAnteriorKwh, 1)}
            </td>
            <td className="px-3 py-3 text-muted-foreground">
              {[
                item.estimado ? 'Leitura estimada' : '',
                item.trocaMedidor ? 'Troca de medidor: consumo estimado pela mediana da UC' : '',
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
}: {
  texto: string | null
  efeitos?: {
    consumo: number | string
    tarifa: number | string
    bandeira: number | string
    outros: number | string
  } | null
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
                    {formatarMoeda(valor)}
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
        <SemDados mensagem="A explicação da conta ainda não está disponível." />
      )}
    </div>
  )

  return conteudo
}

export function Faturas({
  dados,
}: {
  dados: FaturaUC[]
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
                {fatura.diasAtraso === null
                  ? 'Atraso não informado'
                  : fatura.diasAtraso <= 0
                    ? 'Em dia'
                    : `${fatura.diasAtraso} dias`}
              </td>
            </tr>
          ))}
        </Tabela>
      )}
    </div>
  )

  return conteudo
}

export function Interrupcoes({
  dados,
  alimentador,
}: {
  dados: InterrupcaoUC[]
  alimentador?: { nome: string; interrupcoes: number; dec: string }
}) {
  const conteudo = (
    <div className="space-y-4">
      {alimentador && (
        <div className="rounded-md border bg-muted/30 p-3 text-sm">
          <p className="font-medium">Resumo do alimentador {alimentador.nome}</p>
          <p className="mt-1 text-muted-foreground">
            {alimentador.interrupcoes} interrupção(ões) · DEC: {formatarNumero(alimentador.dec, 2)} h
          </p>
        </div>
      )}
      {dados.length === 0 ? (
        <SemDados mensagem="Nenhuma interrupção registrada." />
      ) : (
        <Tabela colunas={['Data', 'Duração bruta', 'Duração efetiva', 'Sobreposição', 'Causa']}>
          {dados.map((interrupcao) => (
            <tr key={interrupcao.id}>
              <td className="px-3 py-3">{interrupcao.data}</td>
              <td className="px-3 py-3">{interrupcao.duracaoBruta ?? interrupcao.duracao}</td>
              <td className="px-3 py-3">{interrupcao.duracao}</td>
              <td className="px-3 py-3">{interrupcao.sobreposicao ? 'Sim' : 'Não'}</td>
              <td className="px-3 py-3">{interrupcao.causa}</td>
            </tr>
          ))}
        </Tabela>
      )}
    </div>
  )

  return conteudo
}

export function Atendimentos({ dados }: { dados: AtendimentoUC[] }) {
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
        <SemDados mensagem="Nenhum atendimento registrado." />
      ) : (
        <div className="space-y-3">
          {dados.map((atendimento) => {
            const aberto = expandidos.includes(atendimento.id)

            return (
              <div key={atendimento.id} className="rounded-md border">
                <button
                  type="button"
                  aria-expanded={aberto}
                  onClick={() => alternar(atendimento.id)}
                  className="flex w-full items-start justify-between gap-3 p-4 text-left"
                >
                  <span className="space-y-1">
                    <span className="block font-medium">{atendimento.titulo}</span>
                    <span className="block text-xs text-muted-foreground">
                      Protocolo {atendimento.protocolo} · {atendimento.abertura}{atendimento.canal ? ` · ${atendimento.canal}` : ''}
                    </span>
                    <span className="block text-xs text-muted-foreground">
                      {atendimento.status}
                      {atendimento.avaliacao !== null
                        ? ` · Avaliação ${formatarNumero(atendimento.avaliacao, 1)}/5`
                        : ' · Não avaliou'}
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
                    {atendimento.historico.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Nenhum evento registrado.
                      </p>
                    ) : (
                      atendimento.historico.map((evento) => (
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

  return conteudo
}

export function Inspecoes({
  dados,
  ordemAtiva,
  idOrdemAtiva,
  motivoSuspeita,
}: {
  dados: InspecaoUC[]
  ordemAtiva: string | null
  idOrdemAtiva?: string | null
  motivoSuspeita: string | null
}) {
  const conteudo = (
    <div className="space-y-4">
      {ordemAtiva && (
        <div role="status" className="mb-4 rounded-md border p-3 text-sm">
          <p className="flex items-center gap-2 font-medium">
            <AlertCircle className="size-4" />
            <span title={idOrdemAtiva ?? undefined}>Ordem de inspeção ativa: {ordemAtiva}</span>
          </p>
          {motivoSuspeita && (
            <p className="mt-2 text-muted-foreground">Motivos da suspeita: {motivoSuspeita}</p>
          )}
        </div>
      )}

      {dados.length === 0 ? (
        <SemDados mensagem="Nenhuma inspeção registrada." />
      ) : (
        <Tabela colunas={['Data', 'Resultado', 'Origem', 'Tipo de irregularidade']}>
          {dados.map((inspecao) => (
            <tr key={inspecao.id}>
              <td className="px-3 py-3">{inspecao.data}</td>
              <td className="px-3 py-3">{inspecao.resultado.replaceAll('_', ' ').toLowerCase().replace(/^./, (letra) => letra.toUpperCase())}</td>
              <td className="px-3 py-3">{inspecao.origem || "—"}</td>
              <td className="px-3 py-3">{inspecao.tipoIrregularidade || "—"}</td>
            </tr>
          ))}
        </Tabela>
      )}
    </div>
  )

  return conteudo
}
