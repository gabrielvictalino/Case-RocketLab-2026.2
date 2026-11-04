import { useId } from 'react'
import { Info } from 'lucide-react'
import { Link } from 'react-router'
import { Esqueleto } from '@/components/Estados'
import {
  formatarPontosPercentuais,
  formatarVariacao,
} from '@/lib/formatacao'
import { TEXTO_DADOS_INDISPONIVEIS } from '@/components/Estados'

export type SentidoFavoravel = 'alta' | 'baixa' | 'neutro'
export type TipoVariacao = 'percentual' | 'pp'

export interface ParKpi {
  subrotulo: string
  semDados?: boolean
  mensagemComparacao?: string
  valor?: string
  variacao?: number | null
  tipoVariacao?: TipoVariacao
  sentidoFavoravel?: SentidoFavoravel
  valorComparado?: string
}

export interface CartaoKpiProps {
  rotulo: string
  carregando?: boolean
  destino?: string
  semDados?: boolean
  mensagemComparacao?: string
  semPeriodoComparacao?: boolean
  valor?: string
  unidade?: string
  rotuloComparacao?: string
  valorComparado?: string
  variacao?: number | null
  tipoVariacao?: TipoVariacao
  sentidoFavoravel?: SentidoFavoravel
  dica?: string
  pares?: ReadonlyArray<ParKpi>
  indisponivel?: boolean
  mensagemIndisponivel?: string
}

// eslint-disable-next-line react-refresh/only-export-components
export function classeCorVariacao(
  variacao: number | null | undefined,
  sentidoFavoravel: SentidoFavoravel = 'alta',
): string {
  if (
    sentidoFavoravel === 'neutro' || variacao === null ||
    variacao === undefined || variacao === 0
  ) {
    return 've-delta-neutral'
  }
  const favoravel =
    sentidoFavoravel === 'alta' ? variacao > 0 : variacao < 0
  return favoravel ? 've-delta-favorable' : 've-delta-critical'
}

// eslint-disable-next-line react-refresh/only-export-components
export function setaVariacao(variacao: number | null | undefined): string {
  if (variacao === null || variacao === undefined || variacao === 0) {
    return '→'
  }
  return variacao > 0 ? '↑' : '↓'
}

// eslint-disable-next-line react-refresh/only-export-components
export function formatarVariacaoKpi(
  variacao: number,
  tipoVariacao: TipoVariacao = 'percentual',
  casasDecimais = 1,
): string {
  if (tipoVariacao === 'pp') {
    return formatarPontosPercentuais(variacao, casasDecimais, { sinal: true })
  }
  return formatarVariacao(variacao, casasDecimais)
}

export function CartaoKpi({
  rotulo,
  carregando = false,
  destino,
  semDados = false,
  mensagemComparacao,
  semPeriodoComparacao = false,
  valor,
  unidade,
  rotuloComparacao,
  valorComparado,
  variacao,
  tipoVariacao = 'percentual',
  sentidoFavoravel = 'alta',
  dica,
  pares,
  indisponivel = false,
  mensagemIndisponivel = TEXTO_DADOS_INDISPONIVEIS,
}: CartaoKpiProps) {
  const descricaoId = useId()
  const conteudo = (
    <>
      <div className="ve-kpi-label">
        <span>{rotulo}</span>
        {dica && (
          <span className="ve-kpi-hint" title={dica} aria-label={dica}>
            <Info size={14} aria-hidden="true" />
          </span>
        )}
      </div>

      <div id={descricaoId} style={{ display: 'contents' }}>
      {pares && pares.length > 0 ? (
        <>
          <div className="ve-kpi-pair">
            {pares.map((par, idx) => {
              const sentidoPar = par.sentidoFavoravel ?? sentidoFavoravel
              const tipoPar = par.tipoVariacao ?? tipoVariacao
              const classePar = classeCorVariacao(par.variacao, sentidoPar)
              let valorPar = indisponivel ? '—' : (par.valor ?? '—')
              if (par.semDados) valorPar = 'Sem dados no período'
              return (
                <div
                  key={par.subrotulo}
                  className={idx > 0 ? 've-kpi-split' : ''}
                >
                  <div className="ve-kpi-sublabel">{par.subrotulo}</div>
                  <div className="ve-kpi-value ve-num">
                    {carregando && <Esqueleto linhas={1} />}
                    {!carregando && (
                      <span className={par.semDados ? 've-kpi-sem-dados' : undefined}>
                        {valorPar}
                      </span>
                    )}
                  </div>
                  {!indisponivel && !carregando && !par.semDados &&
                    par.variacao !== undefined &&
                    par.variacao !== null && (
                      <div style={{ marginTop: '4px' }}>
                        <span className={`ve-delta ve-delta-chip ${classePar}`}>
                          <span aria-hidden="true">
                            {setaVariacao(par.variacao)}
                          </span>{' '}
                          {formatarVariacaoKpi(par.variacao, tipoPar)}
                        </span>
                      </div>
                    )}
                  {!indisponivel && !carregando &&
                    (par.valorComparado || par.mensagemComparacao) && (
                    <div
                      className="ve-muted"
                      style={{ fontSize: '12px', marginTop: '4px' }}
                    >
                      {par.valorComparado ? (
                        `vs ${par.valorComparado}`
                      ) : (
                        <span className="ve-kpi-sem-dados">{par.mensagemComparacao}</span>
                      )}
                    </div>
                  )}
                </div>
              )
            })}
          </div>
          {indisponivel ? (
            <div className="ve-kpi-foot">
              <span>{mensagemIndisponivel}</span>
            </div>
          ) : (
            (rotuloComparacao || semPeriodoComparacao) && (
              <div className="ve-kpi-foot">
                <span>{semPeriodoComparacao ? 'Sem período de comparação' : 'Comparação'}</span>
                {!semPeriodoComparacao && <span className="ve-num">{rotuloComparacao}</span>}
              </div>
            )
          )}
        </>
      ) : (
        <>
          <div className="ve-kpi-main">
            <div className="ve-kpi-value ve-num">
              {carregando && <Esqueleto linhas={1} />}
              {!carregando && semDados && (
                <span className="ve-kpi-sem-dados">Sem dados no período</span>
              )}
              {!carregando && !semDados && (indisponivel ? '—' : (valor ?? '—'))}
            </div>
            {unidade && !semDados && !carregando && <span className="ve-kpi-unit">{unidade}</span>}
          </div>

          {!indisponivel && !carregando && !semDados &&
            variacao !== undefined && variacao !== null && (
            <div>
              <span
                className={
                  `ve-delta ve-delta-chip ${classeCorVariacao(variacao, sentidoFavoravel)}`
                }
              >
                <span aria-hidden="true">{setaVariacao(variacao)}</span>{' '}
                {formatarVariacaoKpi(variacao, tipoVariacao)}
              </span>
            </div>
          )}

          {indisponivel ? (
            <div className="ve-kpi-foot">
              <span>{mensagemIndisponivel}</span>
            </div>
          ) : (
            (rotuloComparacao || semPeriodoComparacao || valorComparado || mensagemComparacao) && (
              <div className="ve-kpi-foot">
                <span>
                  {semPeriodoComparacao
                    ? 'Sem período de comparação'
                    : (rotuloComparacao ?? 'Comparação')}
                </span>
                {(valorComparado || mensagemComparacao) && (
                  <span className={valorComparado ? 've-num' : 've-kpi-sem-dados'}>
                    {valorComparado ?? mensagemComparacao}
                  </span>
                )}
              </div>
            )
          )}
        </>
      )}
      </div>
    </>
  )
  return destino ? (
    <Link
      className="ve-kpi ve-kpi-link"
      to={destino}
      aria-label={`${rotulo} · ver detalhe`}
      aria-describedby={descricaoId}
    >
      {conteudo}
    </Link>
  ) : (
    <article className="ve-kpi" aria-label={rotulo}>{conteudo}</article>
  )
}
