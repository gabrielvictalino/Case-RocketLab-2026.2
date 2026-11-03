import { describe, expect, it } from 'vitest'
import { ErroApi } from '@/lib/api/cliente'
import {
  acoesDisponiveis,
  INSPETORES,
  mensagemErro,
  montarPayload,
  somarEnergia,
  validarFormulario,
  type Valores,
} from './ordens'
const v: Valores = {
  inspetor: '',
  observacao: '',
  motivo: '',
  resultado: 'IRREGULARIDADE CONFIRMADA',
  tipo_irregularidade: '',
  kwh_recuperado: '0',
  data: '2020-01-01',
}
describe('ordens de inspeção', () => {
  it('oferece ações por status', () => {
    expect(acoesDisponiveis('ABERTA')).toEqual(['despachar', 'cancelar'])
    expect(acoesDisponiveis('EM_CAMPO')).toEqual([
      'tentativas',
      'resultado',
      'cancelar',
    ])
    expect(acoesDisponiveis('CONCLUIDA')).toEqual([])
    expect(acoesDisponiveis('CANCELADA')).toEqual([])
  })
  it('valida resultado, texto e inspetor sem converter energia', () => {
    expect(validarFormulario('resultado', v)).toHaveProperty(
      'tipo_irregularidade',
    )
    expect(validarFormulario('resultado', v)).toHaveProperty('kwh_recuperado')
    expect(
      validarFormulario('resultado', {
        ...v,
        tipo_irregularidade: 'tipo',
        kwh_recuperado: '12,5',
      }),
    ).toEqual({})
    expect(
      validarFormulario('resultado', { ...v, data: '2999-01-01' }),
    ).toHaveProperty('data')
    expect(
      validarFormulario('resultado', {
        ...v,
        tipo_irregularidade: 'tipo',
        kwh_recuperado: '1e2',
      }),
    ).toHaveProperty('kwh_recuperado')
    expect(validarFormulario('despachar', v)).toHaveProperty('inspetor')
    expect(
      validarFormulario('tentativas', { ...v, observacao: '  ' }),
    ).toHaveProperty('observacao')
    expect(
      validarFormulario('cancelar', { ...v, motivo: '  ' }),
    ).toHaveProperty('motivo')
  })
  it('valida datas reais do calendário', () => {
    const valores = { ...v, resultado: 'SEM IRREGULARIDADE' }
    expect(
      validarFormulario('resultado', { ...valores, data: '2026-02-30' }),
    ).toHaveProperty('data')
    expect(
      validarFormulario('resultado', { ...valores, data: '2026-13-01' }),
    ).toHaveProperty('data')
    expect(
      validarFormulario('resultado', { ...valores, data: '2024-02-29' }),
    ).not.toHaveProperty('data')
  })
  it('monta payload e lista inspetores', () => {
    expect(
      montarPayload('resultado', { ...v, resultado: 'SEM IRREGULARIDADE' }),
    ).toEqual({
      resultado: 'SEM IRREGULARIDADE',
      tipo_irregularidade: null,
      kwh_recuperado: '0',
      data: '2020-01-01',
    })
    expect(
      montarPayload('resultado', {
        ...v,
        tipo_irregularidade: ' fio ',
        kwh_recuperado: '12,5',
      }),
    ).toMatchObject({ tipo_irregularidade: 'fio', kwh_recuperado: '12.5' })
    expect(INSPETORES).toHaveLength(40)
    expect(INSPETORES[0]).toBe('INSP-001')
    expect(INSPETORES[39]).toBe('INSP-040')
  })
  it('soma centavos exatamente', () => {
    expect(somarEnergia(['0.10', '0.20'])).toBe('0.30')
    expect(somarEnergia(['9999999999999999.99', '0.01'])).toBe(
      '10000000000000000.00',
    )
  })
  it('apresenta erros sem código', () => {
    expect(mensagemErro(new ErroApi(403))).toContain('cargo')
    expect(mensagemErro(new ErroApi(409))).toContain('será atualizada')
    expect(mensagemErro(new ErroApi(404))).toContain('não encontrada')
    expect(
      mensagemErro(new ErroApi(422, { detail: [{ mensagem: 'inválido' }] })),
    ).toContain('inválido')
    expect(mensagemErro(new ErroApi(422, { detail: {} }))).toBe(
      'Confira os campos do formulário.',
    )
    expect(mensagemErro(new ErroApi(500))).toContain('Tente novamente')
  })
})
