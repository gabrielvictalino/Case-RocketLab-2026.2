import { useEffect, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { Navigate, Outlet, useLocation } from 'react-router'
import { useSessao } from '@/lib/auth/sessao'

export function RotaProtegida({ children }: { children?: ReactNode }) {
  const sessao = useSessao()
  const location = useLocation()
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!sessao) {
      queryClient.clear()
    }
  }, [sessao, queryClient])

  if (!sessao) {
    const caminhoAtual = `${location.pathname}${location.search}`
    const parametroRetorno = encodeURIComponent(caminhoAtual)
    return <Navigate to={`/login?retorno=${parametroRetorno}`} replace />
  }

  return children ? <>{children}</> : <Outlet />
}
