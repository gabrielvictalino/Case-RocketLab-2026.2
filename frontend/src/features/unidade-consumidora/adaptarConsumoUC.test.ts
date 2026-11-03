import { describe, expect, it } from 'vitest'
import { adaptarConsumoUC } from './adaptarConsumoUC'
import type { VisaoUC } from './useUnidadeConsumidora'

describe('adaptarConsumoUC', () => {
  it('converte consumo atual e anterior preservando os indicadores', () => {
    const consumo: VisaoUC['consumo'] = {
      competencia_inicial: '2026-01-01',
      competencia_final: '2026-01-01',
      meses: [
        {
          competencia: '2026-01-01',
          atual: {
            competencia: '2026-01-01',
            consumo_kwh: '250',
            leitura_estimada: true,
            troca_medidor: true,
            consumo_ajustado: false,
          },
          anterior: {
            competencia: '2025-01-01',
            consumo_kwh: '200',
            leitura_estimada: false,
            troca_medidor: false,
            consumo_ajustado: false,
          },
        },
      ],
    }

    expect(adaptarConsumoUC(consumo)).toEqual([
      {
        competencia: 'jan/2026',
        consumoKwh: 250,
        consumoAnoAnteriorKwh: 200,
        estimado: true,
        trocaMedidor: true,
      },
    ])
  })

  it('preserva meses sem leitura como valores ausentes', () => {
    const consumo: VisaoUC['consumo'] = {
      competencia_inicial: '2026-02-01',
      competencia_final: '2026-02-01',
      meses: [
        {
          competencia: '2026-02-01',
          atual: null,
          anterior: null,
        },
      ],
    }

    expect(adaptarConsumoUC(consumo)).toEqual([
      {
        competencia: 'fev/2026',
        consumoKwh: null,
        consumoAnoAnteriorKwh: null,
        estimado: false,
        trocaMedidor: false,
      },
    ])
  })
})
