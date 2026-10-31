import { describe, expect, it } from 'vitest'
import {
  atualizarRecorteUrl,
  lerRecortesUrl,
  limparRecortesUrl,
  temRecorteAtivo,
} from '@/lib/recortes'

describe('utilitários de recortes na URL', () => {
  it('lê recortes válidos e ignora bairro órfão sem município', () => {
    const comMunicipio = new URLSearchParams(
      'municipio=Recife&bairro=Boa+Viagem&classe=Residencial&alimentador=AL-01&atipico=1',
    )
    expect(lerRecortesUrl(comMunicipio)).toEqual({
      municipio: 'Recife',
      bairro: 'Boa Viagem',
      classe: 'Residencial',
      alimentador: 'AL-01',
      atipico: true,
    })

    const semMunicipio = new URLSearchParams('bairro=Boa+Viagem&atipico=0')
    expect(lerRecortesUrl(semMunicipio)).toEqual({
      municipio: '',
      bairro: '',
      classe: '',
      alimentador: '',
      atipico: false,
    })
  })

  it('limpa bairro ao trocar ou limpar o município e preserva periodo/comparacao', () => {
    const inicial = new URLSearchParams(
      'periodo=2025-07..2026-06&comparacao=2024-07..2025-06&municipio=Recife&bairro=Boa+Viagem&classe=Comercial',
    )

    const trocouMunicipio = atualizarRecorteUrl(inicial, {
      municipio: 'Olinda',
    })
    expect(trocouMunicipio.get('municipio')).toBe('Olinda')
    expect(trocouMunicipio.get('bairro')).toBeNull()
    expect(trocouMunicipio.get('classe')).toBe('Comercial')
    expect(trocouMunicipio.get('periodo')).toBe('2025-07..2026-06')
    expect(trocouMunicipio.get('comparacao')).toBe('2024-07..2025-06')

    const limpouMunicipio = atualizarRecorteUrl(inicial, { municipio: '' })
    expect(limpouMunicipio.get('municipio')).toBeNull()
    expect(limpouMunicipio.get('bairro')).toBeNull()
  })

  it('Limpar filtros remove apenas os recortes e preserva periodo, comparacao e aba', () => {
    const params = new URLSearchParams(
      'periodo=2025-07..2026-06&comparacao=2024-07..2025-06&aba=fila&municipio=Recife&bairro=Pina&classe=Industrial&alimentador=AL-02&atipico=1',
    )

    const limpo = limparRecortesUrl(params)
    expect(limpo.get('periodo')).toBe('2025-07..2026-06')
    expect(limpo.get('comparacao')).toBe('2024-07..2025-06')
    expect(limpo.get('aba')).toBe('fila')
    expect(limpo.get('municipio')).toBeNull()
    expect(limpo.get('bairro')).toBeNull()
    expect(limpo.get('classe')).toBeNull()
    expect(limpo.get('alimentador')).toBeNull()
    expect(limpo.get('atipico')).toBeNull()
  })

  it('identifica se há algum recorte ativo', () => {
    expect(temRecorteAtivo({})).toBe(false)
    expect(temRecorteAtivo({ municipio: 'Recife' })).toBe(true)
    expect(temRecorteAtivo({ atipico: true })).toBe(true)
  })
})
