import { Navigate, useParams } from 'react-router'

export function RedirecionarRotaUc() {
  const { id } = useParams<{ id: string }>()
  return <Navigate to={`/unidade-consumidora?uc=${encodeURIComponent(id ?? "")}`} replace />
}
