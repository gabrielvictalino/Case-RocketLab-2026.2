import { Outlet } from 'react-router'
import { NavegacaoLateral } from '@/app/layout/NavegacaoLateral'

export function LayoutPrincipal() {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <NavegacaoLateral />
      <div className="flex flex-1 flex-col">
        <header className="h-14 border-b bg-card px-6" />
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
