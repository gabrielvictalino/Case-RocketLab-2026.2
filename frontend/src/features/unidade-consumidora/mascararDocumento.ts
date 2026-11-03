export function mascararDocumento(documento: string): string {
  const digitos = documento.replace(/\D/g, '')

  if (digitos.length === 11) {
    return `***.${digitos.slice(3, 6)}.${digitos.slice(6, 9)}-**`
  }

  if (digitos.length === 14) {
    return `**.${digitos.slice(2, 5)}.${digitos.slice(5, 8)}/****-**`
  }

  return documento.includes('*') ? documento : 'Documento indisponível'
}
