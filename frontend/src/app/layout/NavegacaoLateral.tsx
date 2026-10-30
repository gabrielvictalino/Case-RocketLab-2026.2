import { NavLink } from 'react-router'
import { cn } from '@/lib/utils'

export interface ItemNavegacao {
  caminho: string
  rotulo: string
}

// eslint-disable-next-line react-refresh/only-export-components
export const ITENS_NAVEGACAO: readonly ItemNavegacao[] = [
  { caminho: '/visao-geral', rotulo: 'Visão Geral' },
  { caminho: '/receita', rotulo: 'Receita' },
  { caminho: '/unidade-consumidora', rotulo: 'Unidade Consumidora' },
  { caminho: '/perdas', rotulo: 'Perdas' },
  { caminho: '/operacao', rotulo: 'Operação' },
]

export function NavegacaoLateral() {
  return (
    <aside
      aria-label="Navegação principal"
      className="w-64 shrink-0 border-r bg-card p-4"
    >
      <div className="mb-6 px-2">
        <span className="text-lg font-semibold tracking-tight">
          V-Energy Grid 360
        </span>
      </div>
      <nav className="flex flex-col gap-1">
        {ITENS_NAVEGACAO.map((item) => (
          <NavLink
            key={item.caminho}
            to={item.caminho}
            className={({ isActive }) =>
              cn(
                'rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
              )
            }
          >
            {item.rotulo}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
