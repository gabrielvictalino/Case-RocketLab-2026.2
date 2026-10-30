import { useQueryClient } from '@tanstack/react-query'
import { Outlet } from 'react-router'
import { NavegacaoLateral } from '@/app/layout/NavegacaoLateral'
import { BarraPeriodo } from '@/app/periodo/BarraPeriodo'
import { Button } from '@/components/ui/button'
import { encerrarSessao, useSessao } from '@/lib/auth/sessao'

export function LayoutPrincipal() {
  const sessao = useSessao()
  const queryClient = useQueryClient()

  function aoSair() {
    queryClient.clear()
    encerrarSessao()
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <NavegacaoLateral />
      <div className="flex flex-1 flex-col">
        <header className="sticky top-0 z-10 flex min-h-14 flex-wrap items-center justify-between gap-4 border-b bg-card px-6 py-2">
          <BarraPeriodo />
          <div className="flex items-center gap-3 border-l pl-4">
            {sessao ? (
              <span className="text-muted-foreground text-xs font-medium">
                {sessao.login}
              </span>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={aoSair}
            >
              Sair
            </Button>
          </div>
        </header>
        <main className="flex-1 p-6">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
