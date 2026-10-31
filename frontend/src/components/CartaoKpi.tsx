import { Info } from 'lucide-react'
import {
  formatarPontosPercentuais,
  formatarVariacao,
} from '@/lib/formatacao'
import { TEXTO_DADOS_INDISPONIVEIS } from '@/components/Estados'

export type SentidoFavoravel = 'alta' | 'baixa'
export type TipoVariacao = 'percentual' | 'pp'

export interface ParKpi {
  subrotulo: string
  valor?: string
  variacao?: number | null
  tipoVariacao?: TipoVariacao
  sentidoFavoravel?: SentidoFavoravel
  valorComparado?: string
}

export interface CartaoKpiProps {
  rotulo: string
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
  if (variacao === null || variacao === undefined || variacao === 0) {
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
  return (
    <article className="ve-kpi" aria-label={rotulo}>
      <div className="ve-kpi-label">
        <span>{rotulo}</span>
        {dica && (
          <span className="ve-kpi-hint" title={dica} aria-label={dica}>
            <Info size={14} aria-hidden="true" />
          </span>
        )}
      </div>

      {pares && pares.length > 0 ? (
        <>
          <div className="ve-kpi-pair">
            {pares.map((par, idx) => {
              const sentidoPar = par.sentidoFavoravel ?? sentidoFavoravel
              const tipoPar = par.tipoVariacao ?? tipoVariacao
              const classePar = classeCorVariacao(par.variacao, sentidoPar)
              return (
                <div
                  key={par.subrotulo}
                  className={idx > 0 ? 've-kpi-split' : ''}
                >
                  <div className="ve-kpi-sublabel">{par.subrotulo}</div>
                  <div className="ve-kpi-value ve-num">
                    {indisponivel ? '—' : (par.valor ?? '—')}
                  </div>
                  {!indisponivel &&
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
                  {!indisponivel && par.valorComparado && (
                    <div
                      className="ve-muted"
                      style={{ fontSize: '12px', marginTop: '4px' }}
                    >
                      vs {par.valorComparado}
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
            rotuloComparacao && (
              <div className="ve-kpi-foot">
                <span>Comparação</span>
                <span className="ve-num">{rotuloComparacao}</span>
              </div>
            )
          )}
        </>
      ) : (
        <>
          <div className="ve-kpi-main">
            <span className="ve-kpi-value ve-num">
              {indisponivel ? '—' : (valor ?? '—')}
            </span>
            {unidade && <span className="ve-kpi-unit">{unidade}</span>}
          </div>

          {!indisponivel && variacao !== undefined && variacao !== null && (
            <div>
              <span
                className={`ve-delta ve-delta-chip ${classeCorVariacao(variacao, sentidoFavoravel)}`}
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
            (rotuloComparacao || valorComparado) && (
              <div className="ve-kpi-foot">
                <span>{rotuloComparacao ?? 'Comparação'}</span>
                {valorComparado && (
                  <span className="ve-num">{valorComparado}</span>
                )}
              </div>
            )
          )}
        </>
      )}
    </article>
  )
}
