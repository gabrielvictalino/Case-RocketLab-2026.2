import type { ReactNode } from 'react'

export type VarianteEtiqueta =
  | 'padrao'
  | 'marca'
  | 'favoravel'
  | 'desfavoravel'
  | 'atencao'
  | 'critico'

export interface EtiquetaProps {
  variante?: VarianteEtiqueta
  ponto?: boolean
  className?: string
  children: ReactNode
}

const CLASSE_VARIANTE: Record<VarianteEtiqueta, string> = {
  padrao: '',
  marca: 've-badge-brand',
  favoravel: 've-badge-favorable',
  desfavoravel: 've-badge-unfavorable',
  atencao: 've-badge-attention',
  critico: 've-badge-critical',
}

export function Etiqueta({
  variante = 'padrao',
  ponto = false,
  className = '',
  children,
}: EtiquetaProps) {
  return (
    <span
      className={`ve-badge ${CLASSE_VARIANTE[variante]} ${ponto ? 've-badge-dot' : ''} ${className}`.trim()}
    >
      {children}
    </span>
  )
}
