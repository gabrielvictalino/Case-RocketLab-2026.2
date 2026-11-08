import { api, desembrulhar } from '@/lib/api/cliente'
import { baixarArquivo } from '@/lib/exportacao'
import type { components } from '@/lib/api/schema'

export type PreviaImportacao = components['schemas']['PreviaImportacao']
export type ImportacaoConfirmada = components['schemas']['ImportacaoConfirmada']
export const CHAVE_ULTIMA_IMPORTACAO = ['importacao-ultima'] as const
export const FALHA_AO_EXPORTAR = 'Não foi possível exportar a planilha. Tente novamente.'

export async function exportarFila(recortes: {
  municipio: string
  bairro: string
  classe: string
}): Promise<void> {
  const planilha = await desembrulhar(
    api.GET('/api/v1/perdas/fila/export', {
      params: {
        query: {
          ...(recortes.municipio && { municipio: recortes.municipio }),
          ...(recortes.bairro && { bairro: recortes.bairro }),
          ...(recortes.classe && { classe: recortes.classe }),
        },
      },
      parseAs: 'blob',
    }),
  )
  baixarArquivo(planilha, 'fila-de-inspecao.xlsx')
}

export async function exportarPlanilhaCampo(): Promise<void> {
  const planilha = await desembrulhar(
    api.GET('/api/v1/ordens-inspecao/export', { parseAs: 'blob' }),
  )
  baixarArquivo(planilha, 'planilha-de-campo.xlsx')
}

export function enviarPlanilha(arquivo: File): Promise<PreviaImportacao> {
  return desembrulhar(
    api.POST('/api/v1/ordens-inspecao/importacoes', {
      // O OpenAPI descreve o upload como string; quem chega aqui é o próprio arquivo.
      body: { arquivo: arquivo as unknown as string },
      bodySerializer: (corpo) => {
        const formulario = new FormData()
        formulario.append('arquivo', corpo.arquivo)
        return formulario
      },
    }),
  )
}

export function confirmarPlanilha(id: string): Promise<ImportacaoConfirmada> {
  return desembrulhar(
    api.POST('/api/v1/ordens-inspecao/importacoes/{id_}/confirmar', {
      params: { path: { id_: id } },
    }),
  )
}

export function buscarUltimaImportacao(): Promise<ImportacaoConfirmada | null> {
  return desembrulhar(api.GET('/api/v1/ordens-inspecao/importacoes/ultima'))
}
