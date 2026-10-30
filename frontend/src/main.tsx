import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { RouterProvider } from 'react-router'
import { Providers } from '@/app/providers'
import { criarRouter } from '@/app/rotas'
import '@/index.css'

const router = criarRouter()
const elementoRaiz = document.getElementById('root')

if (!elementoRaiz) {
  throw new Error('Elemento #root não encontrado no index.html')
}

createRoot(elementoRaiz).render(
  <StrictMode>
    <Providers>
      <RouterProvider router={router} />
    </Providers>
  </StrictMode>,
)
