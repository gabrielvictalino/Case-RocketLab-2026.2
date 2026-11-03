import { describe, expect, it } from 'vitest'
import { mascararDocumento } from './mascararDocumento'

describe('mascararDocumento', () => {
  it('mascara CPF com ou sem pontuacao', () => {
    expect(mascararDocumento('12345678901')).toBe('***.456.789-**')
    expect(mascararDocumento('123.456.789-01')).toBe('***.456.789-**')
  })

  it('mascara CNPJ com ou sem pontuacao', () => {
    expect(mascararDocumento('12345678000190')).toBe('**.345.678/****-**')
    expect(mascararDocumento('12.345.678/0001-90')).toBe('**.345.678/****-**')
  })

  it('preserva um documento ja mascarado', () => {
    expect(mascararDocumento('***.456.789-**')).toBe('***.456.789-**')
  })

  it('nao exibe documentos invalidos', () => {
    expect(mascararDocumento('123')).toBe('Documento indisponível')
  })
})

