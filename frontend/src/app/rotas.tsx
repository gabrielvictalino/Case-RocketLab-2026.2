
import {
  createBrowserRouter,
  Navigate,
  type RouteObject,
} from 'react-router'
import { LayoutPrincipal } from '@/app/layout/LayoutPrincipal'
import { PaginaNaoEncontrada } from '@/app/PaginaNaoEncontrada'
import { PaginaOperacao } from '@/features/operacao/PaginaOperacao'
import { PaginaPerdas } from '@/features/perdas/PaginaPerdas'
import { PaginaReceita } from '@/features/receita/PaginaReceita'
import { PaginaUnidadeConsumidora } from '@/features/unidade-consumidora/PaginaUnidadeConsumidora'
import { PaginaVisaoGeral } from '@/features/visao-geral/PaginaVisaoGeral'

export const rotas: RouteObject[] = [
  {
    path: '/',
    element: <LayoutPrincipal />,
    children: [
      {
        index: true,
        element: <Navigate to="/visao-geral" replace />,
      },
      {
        path: 'visao-geral',
        element: <PaginaVisaoGeral />,
      },
      {
        path: 'receita',
        element: <PaginaReceita />,
      },
      {
        path: 'unidade-consumidora',
        element: <PaginaUnidadeConsumidora />,
      },
      {
        path: 'ucs/:id',
        element: <PaginaUnidadeConsumidora />,
      },
      {
        path: 'perdas',
        element: <PaginaPerdas />,
      },
      {
        path: 'operacao',
        element: <PaginaOperacao />,
      },
      {
        path: '*',
        element: <PaginaNaoEncontrada />,
      },
    ],
  },
]

export function criarRouter() {
  return createBrowserRouter(rotas)
}
