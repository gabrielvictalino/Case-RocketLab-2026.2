import { useState } from 'react'
import { Outlet } from 'react-router'
import { NavegacaoLateral } from '@/app/layout/NavegacaoLateral'
import { BarraPeriodo } from '@/app/periodo/BarraPeriodo'
import { PainelAgente } from '@/features/assistente/PainelAgente'

export function LayoutPrincipal() {
  const [agenteAberto, setAgenteAberto] = useState(false)

  return (
    <div
      className="ve-root"
      data-theme="light"
      style={{
        position: 'relative',
        display: 'flex',
        flexWrap: 'nowrap',
        alignItems: 'stretch',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--surface)',
        color: 'var(--ink)',
      }}
    >
      <NavegacaoLateral
        agenteAberto={agenteAberto}
        aoAlternarAgente={() => setAgenteAberto((aberto) => !aberto)}
      />
      <div
        style={{
          flex: '1 1 auto',
          minWidth: 0,
          height: '100%',
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <BarraPeriodo />
        <main
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '24px',
            padding: '24px',
            maxWidth: '1400px',
            width: '100%',
            flex: 1,
          }}
        >
          <Outlet />
        </main>
      </div>
      <PainelAgente
        aberto={agenteAberto}
        aoFechar={() => setAgenteAberto(false)}
      />
    </div>
  )
}
