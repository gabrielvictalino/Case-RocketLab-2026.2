import type { components } from '@/lib/api/schema'
import { ErroApi } from '@/lib/api/cliente'
import { lerRecortesUrl } from '@/lib/recortes'

export type ContextoPergunta = components['schemas']['ContextoPergunta']
export type RespostaPergunta = components['schemas']['RespostaPergunta']
export type Tela = NonNullable<ContextoPergunta['tela']>

export const ROTULO_TELA: Record<Tela, string> = {
  'visao-geral': 'Visão Geral',
  receita: 'Receita',
  'unidade-consumidora': 'Unidade Consumidora',
  perdas: 'Perdas',
  operacao: 'Operação',
}

const ROTULO_RECORTE: Record<string, string> = {
  municipio: 'Município',
  bairro: 'Bairro',
  classe: 'Classe',
  alimentador: 'Alimentador',
  id_uc: 'UC',
}

export interface Troca {
  id: string
  pergunta: string
  contexto: ContextoPergunta
  estado: 'pendente' | 'respondida' | 'falhou'
  resposta?: RespostaPergunta
  erro?: string
}

export function telaDaRota(caminho: string): Tela | null {
  const segmento = caminho.split('/').filter(Boolean)[0] ?? ''
  return segmento in ROTULO_TELA ? (segmento as Tela) : null
}

/** O que a tela aberta sabe: período e comparação da barra, recortes e UC da URL. */
export function contextoDaTela(
  caminho: string,
  busca: URLSearchParams,
  periodo: { periodo: string; comparacao?: string } | null,
): ContextoPergunta {
  const tela = telaDaRota(caminho)
  const url = lerRecortesUrl(busca)
  const recortes: Record<string, string> = {}
  for (const chave of ['municipio', 'bairro', 'classe', 'alimentador'] as const) {
    if (url[chave]) {
      recortes[chave] = url[chave]
    }
  }
  const uc = (busca.get('uc') ?? '').trim()
  if (tela === 'unidade-consumidora' && uc) {
    recortes.id_uc = uc
  }
  return {
    tela,
    periodo: periodo?.periodo ?? null,
    comparacao: periodo?.comparacao ?? null,
    recortes,
  }
}

export function rotulosDosRecortes(contexto: ContextoPergunta): string[] {
  return Object.entries(contexto.recortes ?? {}).map(
    ([chave, valor]) => `${ROTULO_RECORTE[chave] ?? chave}: ${valor}`,
  )
}

const MENSAGEM_LIMITE_NGINX =
  'Muitas requisições em pouco tempo. Espere alguns segundos e pergunte de novo.'

const MENSAGEM_POR_CODIGO: Partial<Record<string, string>> = {
  LIMITE_DE_PERGUNTAS:
    'Você fez muitas perguntas em pouco tempo. Espere um pouco e pergunte de novo.',
  COTA_DE_TOKENS_ESGOTADA:
    'A cota diária do assistente acabou. Ela volta à meia-noite.',
  limite_requisicoes: MENSAGEM_LIMITE_NGINX,
  ASSISTENTE_INDISPONIVEL: 'O assistente não está configurado neste ambiente.',
  PROVEDOR_INDISPONIVEL:
    'O provedor do modelo de IA está fora do ar. Tente de novo em instantes.',
  ASSISTENTE_TEMPO_ESGOTADO:
    'O assistente demorou demais para responder. Tente de novo ou simplifique a pergunta.',
  BANCO_INDISPONIVEL:
    'O banco de dados do assistente está fora do ar. Tente de novo em instantes.',
  BASE_INDISPONIVEL: 'Ainda não há uma carga de dados publicada.',
  CONVERSA_NAO_ENCONTRADA:
    'A conversa anterior expirou. Comece uma nova conversa.',
}

/** Mensagem própria para cada erro do assistente, principalmente 429 e 503. */
export function mensagemDeErro(erro: unknown): string {
  if (!(erro instanceof ErroApi)) {
    return 'Não foi possível falar com o assistente. Verifique a conexão e tente de novo.'
  }
  const porCodigo = MENSAGEM_POR_CODIGO[erro.code]
  if (porCodigo && erro.code === 'LIMITE_DE_PERGUNTAS' && erro.message) {
    // O backend diz em quantos segundos dá para perguntar de novo.
    return erro.message
  }
  if (porCodigo) {
    return porCodigo
  }
  if (erro.status === 429) {
    return MENSAGEM_LIMITE_NGINX
  }
  if (erro.status === 503) {
    return 'O assistente está indisponível agora. Tente de novo em instantes.'
  }
  if (erro.status === 422) {
    return 'A pergunta ou o contexto da tela não são válidos. Revise e tente de novo.'
  }
  return 'O assistente não conseguiu responder. Tente de novo.'
}
