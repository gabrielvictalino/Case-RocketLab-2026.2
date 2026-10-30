import { useState, type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactQueryDevtools } from '@tanstack/react-query-devtools'
import { ErroApi } from '@/lib/api/cliente'

const CINCO_MINUTOS_MS = 5 * 60 * 1000

function deveTentarNovamente(failureCount: number, error: unknown): boolean {
  if (error instanceof ErroApi && error.status >= 400 && error.status < 500) {
    return false
  }
  if (
    error !== null &&
    typeof error === 'object' &&
    'status' in error &&
    typeof (error as { status: unknown }).status === 'number'
  ) {
    const status = (error as { status: number }).status
    if (status >= 400 && status < 500) {
      return false
    }
  }
  return failureCount < 1
}

// eslint-disable-next-line react-refresh/only-export-components
export function criarQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: CINCO_MINUTOS_MS,
        refetchOnWindowFocus: false,
        retry: deveTentarNovamente,
      },
    },
  })
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(criarQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {import.meta.env.DEV ? (
        <ReactQueryDevtools initialIsOpen={false} />
      ) : null}
    </QueryClientProvider>
  )
}
