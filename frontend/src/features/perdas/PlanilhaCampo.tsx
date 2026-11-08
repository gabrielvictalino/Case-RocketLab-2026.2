import { useCallback, useRef, useState, type ChangeEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Dialogo } from '@/components/Dialogo'
import type { ErroApi } from '@/lib/api/cliente'
import {
  buscarUltimaImportacao,
  CHAVE_ULTIMA_IMPORTACAO,
  confirmarPlanilha,
  enviarPlanilha,
  exportarPlanilhaCampo,
  FALHA_AO_EXPORTAR,
  type ImportacaoConfirmada,
  type PreviaImportacao,
} from './planilhas'

const contagem = (quantidade: number, singular: string, plural: string) =>
  `${quantidade} ${quantidade === 1 ? singular : plural}`

export function PlanilhaCampo({ podeEscrever }: { podeEscrever: boolean }) {
  const cliente = useQueryClient()
  const entrada = useRef<HTMLInputElement>(null)
  const botaoImportar = useRef<HTMLButtonElement>(null)
  const focoAoFechar = useCallback(() => botaoImportar.current, [])
  const [previa, setPrevia] = useState<PreviaImportacao | null>(null)
  const [concluida, setConcluida] = useState<ImportacaoConfirmada | null>(null)
  const [erro, setErro] = useState<string | null>(null)
  const ultima = useQuery({
    queryKey: CHAVE_ULTIMA_IMPORTACAO,
    queryFn: buscarUltimaImportacao,
  })
  const exportacao = useMutation({
    mutationFn: exportarPlanilhaCampo,
    onMutate: () => setErro(null),
    onError: () => setErro(FALHA_AO_EXPORTAR),
  })
  const envio = useMutation({
    mutationFn: enviarPlanilha,
    onMutate: () => {
      setErro(null)
      setConcluida(null)
    },
    onSuccess: setPrevia,
    onError: (falha: ErroApi) => setErro(falha.message),
  })
  const confirmacao = useMutation({
    mutationFn: confirmarPlanilha,
    onMutate: () => setErro(null),
    onSuccess: async (resultado) => {
      setPrevia(null)
      setConcluida(resultado)
      await Promise.all(
        [['perdas-fila'], ['ordens-inspecao'], ['kpis'], CHAVE_ULTIMA_IMPORTACAO].map(
          (queryKey) => cliente.invalidateQueries({ queryKey, refetchType: 'all' }),
        ),
      )
    },
    onError: (falha: ErroApi) => setErro(falha.message),
  })
  const escolher = (evento: ChangeEvent<HTMLInputElement>) => {
    const arquivo = evento.target.files?.[0]
    // Limpa o campo para o mesmo arquivo, depois de corrigido, poder ser enviado de novo.
    evento.target.value = ''
    if (arquivo) envio.mutate(arquivo)
  }
  const fechar = () => {
    setPrevia(null)
    setErro(null)
  }
  return (
    <>
      <div className="ve-planilha-campo">
        <p>
          {ultima.data
            ? `Última importação: ${ultima.data.arquivo} · ${contagem(ultima.data.atualizadas, 'ordem atualizada', 'ordens atualizadas')}`
            : 'Nenhuma planilha de campo importada.'}
        </p>
        <div className="ve-row">
          <button
            type="button"
            className="ve-btn"
            disabled={exportacao.isPending}
            onClick={() => exportacao.mutate()}
          >
            {exportacao.isPending ? 'Exportando…' : 'Exportar planilha de campo'}
          </button>
          <button
            ref={botaoImportar}
            type="button"
            className="ve-btn"
            disabled={!podeEscrever || envio.isPending}
            title={podeEscrever ? undefined : 'Só o cargo Perdas importa a planilha'}
            onClick={() => entrada.current?.click()}
          >
            {envio.isPending ? 'Lendo planilha…' : 'Importar planilha de campo'}
          </button>
          <input
            ref={entrada}
            type="file"
            hidden
            aria-label="Arquivo da planilha de campo"
            accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={escolher}
          />
        </div>
      </div>
      {erro && !previa && <div role="alert">{erro}</div>}
      {concluida && (
        <div role="status">
          {concluida.arquivo}:{' '}
          {contagem(concluida.atualizadas, 'ordem atualizada', 'ordens atualizadas')}.
          {concluida.rejeitadas.map((linha) => (
            <p key={linha.linha}>
              Linha {linha.linha}: {linha.motivo}
            </p>
          ))}
        </div>
      )}
      {previa && (
        <Dialogo
          aberto
          titulo="Prévia da importação"
          aoFechar={fechar}
          bloqueado={confirmacao.isPending}
          focoAoFechar={focoAoFechar}
        >
          <div className="ve-dialog-form">
            <p>
              <strong>{previa.arquivo}</strong>:{' '}
              {contagem(previa.validas.length, 'linha válida', 'linhas válidas')} ·{' '}
              {contagem(previa.erros.length, 'linha com erro', 'linhas com erro')}
            </p>
            {previa.erros.length > 0 && (
              <ListaLinhas
                titulo="Linhas com erro (não serão aplicadas)"
                linhas={previa.erros}
              />
            )}
            {previa.avisos.length > 0 && (
              <ListaLinhas titulo="Avisos" linhas={previa.avisos} />
            )}
            {erro && <div role="alert">{erro}</div>}
            <div className="ve-row">
              <button
                className="ve-btn"
                type="button"
                disabled={confirmacao.isPending}
                onClick={fechar}
              >
                Voltar
              </button>
              <button
                className="ve-btn ve-btn-primary"
                type="button"
                disabled={confirmacao.isPending || !previa.validas.length}
                onClick={() => confirmacao.mutate(previa.id)}
              >
                Confirmar {contagem(previa.validas.length, 'linha', 'linhas')}
              </button>
            </div>
          </div>
        </Dialogo>
      )}
    </>
  )
}

function ListaLinhas({
  titulo,
  linhas,
}: {
  titulo: string
  linhas: { linha: number; motivo: string }[]
}) {
  return (
    <div>
      <strong>{titulo}</strong>
      <ul className="ve-planilha-lista">
        {linhas.map((linha) => (
          <li key={linha.linha}>
            Linha {linha.linha}: {linha.motivo}
          </li>
        ))}
      </ul>
    </div>
  )
}
