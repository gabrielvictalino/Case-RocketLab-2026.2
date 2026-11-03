import { formatarCompetencia } from '@/lib/formatacao'
import type { VisaoUC } from './useUnidadeConsumidora'
import type { ConsumoMensal } from './SecoesUnidadeConsumidora'

export function adaptarConsumoUC(
  consumo: VisaoUC['consumo'],
): ConsumoMensal[] {
  return consumo.meses.map((mes) => ({
    competencia: formatarCompetencia(mes.competencia),
    consumoKwh: mes.atual ? Number(mes.atual.consumo_kwh) : null,
    consumoAnoAnteriorKwh: mes.anterior
      ? Number(mes.anterior.consumo_kwh)
      : null,
    estimado: mes.atual?.leitura_estimada ?? false,
    trocaMedidor: mes.atual?.troca_medidor ?? false,
  }))
}
