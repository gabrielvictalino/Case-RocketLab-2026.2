import type { components } from '@/lib/api/schema'
import type { ErroApi } from '@/lib/api/cliente'

export const TAMANHO_PAGINA = 25

type Ordem = components['schemas']['Ordem']
export type AcaoOrdem = 'despachar' | 'tentativas' | 'resultado' | 'cancelar'

export function paginaValida(
  total: number,
  itens: number,
  pagina: number,
  tamanho = TAMANHO_PAGINA,
): number | null {
  if (pagina <= 1 || itens !== 0) return null
  return Math.max(1, Math.min(pagina - 1, Math.ceil(total / tamanho)))
}

export function invalidaKpis(acao: AcaoOrdem): boolean {
  return acao === 'resultado'
}
export type Valores = {
  inspetor: string
  observacao: string
  motivo: string
  resultado: string
  tipo_irregularidade: string
  kwh_recuperado: string
  data: string
}
export const INSPETORES = Array.from(
  { length: 40 },
  (_, indice) => `INSP-${String(indice + 1).padStart(3, '0')}`,
)
export const ROTULOS: Record<AcaoOrdem, string> = {
  despachar: 'Despachar',
  tentativas: 'Registrar tentativa',
  resultado: 'Registrar resultado',
  cancelar: 'Cancelar',
}
export function acoesDisponiveis(status: Ordem['status']): AcaoOrdem[] {
  if (status === 'ABERTA') return ['despachar', 'cancelar']
  if (status === 'EM_CAMPO') return ['tentativas', 'resultado', 'cancelar']
  return []
}
export function hojeLocal(): string {
  const data = new Date()
  return `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, '0')}-${String(data.getDate()).padStart(2, '0')}`
}
function dataValida(valor: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(valor)) return false
  const [ano, mes, dia] = valor.split('-').map(Number)
  if (ano === undefined || mes === undefined || dia === undefined) return false
  const data = new Date(ano, mes - 1, dia)
  return (
    data.getFullYear() === ano &&
    data.getMonth() === mes - 1 &&
    data.getDate() === dia
  )
}
export function validarFormulario(
  acao: AcaoOrdem,
  valores: Valores,
): Record<string, string> {
  const erros: Record<string, string> = {}
  const texto = (campo: keyof Valores) => {
    if (!valores[campo].trim() || valores[campo].trim().length > 2000)
      erros[campo] = 'Informe de 1 a 2000 caracteres.'
  }
  if (acao === 'despachar' && !INSPETORES.includes(valores.inspetor))
    erros.inspetor = 'Selecione um inspetor.'
  if (acao === 'tentativas') texto('observacao')
  if (acao === 'cancelar') texto('motivo')
  if (acao === 'resultado') {
    if (
      !['IRREGULARIDADE CONFIRMADA', 'SEM IRREGULARIDADE'].includes(
        valores.resultado,
      )
    )
      erros.resultado = 'Selecione um resultado.'
    if (valores.resultado === 'IRREGULARIDADE CONFIRMADA') {
      texto('tipo_irregularidade')
      const energia = valores.kwh_recuperado.trim()
      if (!/^\d{1,16}([.,]\d{1,2})?$/.test(energia) || !/[1-9]/.test(energia))
        erros.kwh_recuperado =
          'Informe energia maior que zero, com até duas casas decimais.'
    }
    if (!dataValida(valores.data) || valores.data > hojeLocal())
      erros.data = 'Informe uma data válida que não seja futura.'
  }
  return erros
}
export function montarPayload(
  acao: AcaoOrdem,
  valores: Valores,
):
  | components['schemas']['Despacho']
  | components['schemas']['Tentativa']
  | components['schemas']['Cancelamento']
  | components['schemas']['Resultado'] {
  if (acao === 'despachar') return { inspetor: valores.inspetor }
  if (acao === 'tentativas') return { observacao: valores.observacao.trim() }
  if (acao === 'cancelar') return { motivo: valores.motivo.trim() }
  const confirmado = valores.resultado === 'IRREGULARIDADE CONFIRMADA'
  return {
    resultado: confirmado ? 'IRREGULARIDADE CONFIRMADA' : 'SEM IRREGULARIDADE',
    tipo_irregularidade: confirmado ? valores.tipo_irregularidade.trim() : null,
    kwh_recuperado: confirmado
      ? valores.kwh_recuperado.trim().replace(',', '.')
      : '0',
    data: valores.data,
  }
}
export function somarEnergia(valores: string[]): string {
  const centavos = valores.reduce((total, valor) => {
    const [inteiro = '0', fracao = ''] = valor.split('.')
    return (
      total + BigInt(inteiro) * 100n + BigInt(fracao.padEnd(2, '0').slice(0, 2))
    )
  }, 0n)
  return `${centavos / 100n}.${String(centavos % 100n).padStart(2, '0')}`
}
export function mensagemErro(erro: ErroApi): string {
  if (erro.status === 403)
    return 'Seu cargo não tem permissão para gerar ou alterar ordens de inspeção. Só o cargo Perdas pode fazer isso.'
  if (erro.status === 409)
    return 'Esta ordem mudou de estado desde que a lista foi carregada. A lista será atualizada; confira o status atual.'
  if (erro.status === 404)
    return 'Ordem de inspeção não encontrada. A lista será atualizada.'
  if (erro.status === 422) {
    const detalhes = Array.isArray(erro.detail)
      ? erro.detail
          .flatMap((detalhe: unknown) =>
            typeof detalhe === 'object' &&
            detalhe !== null &&
            'mensagem' in detalhe &&
            typeof detalhe.mensagem === 'string'
              ? [detalhe.mensagem]
              : [],
          )
          .join('; ')
      : typeof erro.detail === 'string'
        ? erro.detail
        : ''
    return detalhes
      ? `Confira os campos: ${detalhes}`
      : 'Confira os campos do formulário.'
  }
  return 'Não foi possível concluir a ação. Tente novamente.'
}
