import { useQueryClient } from '@tanstack/react-query'
import {
  Banknote,
  Home,
  LayoutDashboard,
  LogOut,
  MessageSquareText,
  ShieldAlert,
  Zap,
  type LucideIcon,
} from 'lucide-react'
import { NavLink, useSearchParams } from 'react-router'
import {
  cargoDaSessao,
  encerrarSessao,
  ROTULO_CARGO,
  useSessao,
} from '@/lib/auth/sessao'

export interface ItemNavegacao {
  caminho: string
  rotulo: string
  icone: LucideIcon
}

// eslint-disable-next-line react-refresh/only-export-components
export const ITENS_NAVEGACAO: readonly ItemNavegacao[] = [
  { caminho: '/visao-geral', rotulo: 'Visão Geral', icone: LayoutDashboard },
  { caminho: '/receita', rotulo: 'Receita', icone: Banknote },
  {
    caminho: '/unidade-consumidora',
    rotulo: 'Unidade Consumidora',
    icone: Home,
  },
  { caminho: '/perdas', rotulo: 'Perdas', icone: ShieldAlert },
  { caminho: '/operacao', rotulo: 'Operação', icone: Zap },
]

export interface NavegacaoLateralProps {
  agenteAberto?: boolean
  aoAlternarAgente?: () => void
}

export function NavegacaoLateral({
  agenteAberto = false,
  aoAlternarAgente,
}: NavegacaoLateralProps) {
  const [searchParams] = useSearchParams()
  const sessao = useSessao()
  const queryClient = useQueryClient()

  const queryPeriodo = new URLSearchParams()
  const periodo = searchParams.get('periodo')
  const comparacao = searchParams.get('comparacao')
  if (periodo) {
    queryPeriodo.set('periodo', periodo)
  }
  if (comparacao) {
    queryPeriodo.set('comparacao', comparacao)
  }
  const sufixoBusca = queryPeriodo.toString()

  const cargo = cargoDaSessao(sessao?.token)
  const rotuloCargo = cargo ? ROTULO_CARGO[cargo] : null

  function aoSair() {
    queryClient.clear()
    encerrarSessao()
  }

  return (
    <aside
      aria-label="Navegação principal"
      className="ve-nav"
      style={{ flex: '0 0 var(--size-nav)' }}
    >
      <div className="ve-nav-logo">
        <div className="ve-logo">
          <svg
            width="28"
            height="28"
            viewBox="0 0 32 32"
            aria-hidden="true"
            className="ve-logo-mark"
          >
            <rect x="0" y="0" width="32" height="32" rx="7" className="bg" />
            <path
              d="M7 8h5.2L16 19.4 19.8 8H25l-6.6 16h-4.8z"
              className="v"
            />
          </svg>
          <span className="ve-logo-word">
            V-<b>Energy</b>
          </span>
        </div>
      </div>

      <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {ITENS_NAVEGACAO.map(({ caminho, rotulo, icone: Icone }) => {
          const destino = sufixoBusca ? `${caminho}?${sufixoBusca}` : caminho
          return (
            <NavLink key={caminho} to={destino} className="ve-nav-item">
              <Icone size={18} className="ve-icon" aria-hidden="true" />
              <span>{rotulo}</span>
            </NavLink>
          )
        })}
      </nav>

      <div style={{ height: '12px' }} />

      <button
        type="button"
        className="ve-nav-item"
        aria-pressed={agenteAberto}
        onClick={aoAlternarAgente}
      >
        <MessageSquareText size={18} className="ve-icon" aria-hidden="true" />
        <span>Perguntar ao agente</span>
      </button>

      <div className="ve-nav-foot">
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 'var(--space-2)',
          }}
        >
          {sessao ? (
            <div
              style={{
                minWidth: 0,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              <span style={{ color: 'var(--ink)', fontWeight: 500 }}>
                {sessao.login}
              </span>
              {rotuloCargo ? (
                <>
                  {' · '}
                  <span>{rotuloCargo}</span>
                </>
              ) : null}
            </div>
          ) : null}
          <button
            type="button"
            onClick={aoSair}
            className="ve-btn ve-btn-quiet ve-btn-sm"
          >
            <LogOut size={14} aria-hidden="true" />
            <span>Sair</span>
          </button>
        </div>
      </div>
    </aside>
  )
}
