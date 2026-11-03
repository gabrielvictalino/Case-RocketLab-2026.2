import { useEffect, useId, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

const SELETOR_FOCAVEIS =
  'input:not(:disabled), select:not(:disabled), textarea:not(:disabled), button:not(:disabled), [tabindex="0"]'

function focaveis(container: HTMLElement | null): HTMLElement[] {
  return Array.from(
    container?.querySelectorAll<HTMLElement>(SELETOR_FOCAVEIS) ?? [],
  )
}

export function Dialogo({
  aberto,
  titulo,
  aoFechar,
  bloqueado = false,
  children,
  focoAoFechar,
}: {
  aberto: boolean
  titulo: string
  aoFechar: () => void
  bloqueado?: boolean
  children: ReactNode
  focoAoFechar?: () => HTMLElement | null
}) {
  const ref = useRef<HTMLDivElement>(null)
  const id = useId()
  const focoAoFecharRef = useRef(focoAoFechar)
  useEffect(() => {
    focoAoFecharRef.current = focoAoFechar
  }, [focoAoFechar])
  useEffect(() => {
    if (!aberto) return
    const origem =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null
    const root = document.getElementById('root')
    const inertAnterior = root?.inert
    const ariaAnterior = root?.getAttribute('aria-hidden')
    if (root) {
      root.inert = true
      root.setAttribute('aria-hidden', 'true')
    }
    focaveis(ref.current)[0]?.focus()
    return () => {
      if (root) {
        root.inert = inertAnterior ?? false
        if (ariaAnterior === null || ariaAnterior === undefined)
          root.removeAttribute('aria-hidden')
        else root.setAttribute('aria-hidden', ariaAnterior)
      }
      if (origem?.isConnected) origem.focus()
      else focoAoFecharRef.current?.()?.focus()
    }
  }, [aberto])
  if (!aberto) return null
  return createPortal(
    <div
      className="ve-dialog-overlay"
      onMouseDown={(evento) => {
        if (evento.target === evento.currentTarget && !bloqueado) aoFechar()
      }}
    >
      <div
        ref={ref}
        className="ve-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby={id}
        onKeyDown={(evento) => {
          if (evento.key === 'Escape' && !bloqueado) {
            evento.preventDefault()
            aoFechar()
          }
          if (evento.key === 'Tab') {
            const itens = focaveis(ref.current)
            if (!itens.length) {
              evento.preventDefault()
              return
            }
            const indice = itens.indexOf(document.activeElement as HTMLElement)
            if (evento.shiftKey && indice <= 0) {
              evento.preventDefault()
              itens[itens.length - 1]?.focus()
            } else if (!evento.shiftKey && indice === itens.length - 1) {
              evento.preventDefault()
              itens[0]?.focus()
            }
          }
        }}
      >
        <h2 id={id}>{titulo}</h2>
        {children}
      </div>
    </div>,
    document.body,
  )
}
