import { useState, type FormEvent } from 'react'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { api, desembrulhar, ErroApi } from '@/lib/api/cliente'
import type { components } from '@/lib/api/schema'
import { salvarSessao, useSessao } from '@/lib/auth/sessao'

type CredenciaisLogin = components['schemas']['Login']

// eslint-disable-next-line react-refresh/only-export-components
export function resolverDestinoRetorno(retorno: string | null): string {
  if (
    !retorno ||
    !retorno.startsWith('/') ||
    retorno.startsWith('//') ||
    retorno === '/'
  ) {
    return '/visao-geral'
  }
  return retorno
}

export function PaginaLogin() {
  const sessao = useSessao()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()

  const [login, setLogin] = useState('')
  const [senha, setSenha] = useState('')
  const [erro, setErro] = useState<string | null>(null)
  const [enviando, setEnviando] = useState(false)

  const destinoRetorno = resolverDestinoRetorno(searchParams.get('retorno'))

  if (sessao) {
    return <Navigate to={destinoRetorno} replace />
  }

  async function aoSubmeter(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault()
    setErro(null)
    setEnviando(true)

    const corpo: CredenciaisLogin = {
      login: login.trim(),
      senha,
    }

    try {
      const token = await desembrulhar(
        api.POST('/api/v1/auth/login', {
          body: corpo,
        }),
      )
      salvarSessao(token, corpo.login)
      navigate(destinoRetorno, { replace: true })
    } catch (err) {
      if (err instanceof ErroApi && err.status === 401) {
        setErro('Login ou senha inválidos')
      } else if (err instanceof Error) {
        setErro(err.message)
      } else {
        setErro('Não foi possível realizar o login')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4 text-foreground">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-xl">V-Energy Grid 360</CardTitle>
          <CardDescription>
            Entre com suas credenciais para acessar o portal analítico e
            operacional.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={aoSubmeter} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="campo-login">Login</Label>
              <Input
                id="campo-login"
                name="login"
                type="text"
                autoComplete="username"
                required
                value={login}
                onChange={(e) => setLogin(e.target.value)}
                disabled={enviando}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="campo-senha">Senha</Label>
              <Input
                id="campo-senha"
                name="senha"
                type="password"
                autoComplete="current-password"
                required
                value={senha}
                onChange={(e) => setSenha(e.target.value)}
                disabled={enviando}
              />
            </div>

            {erro ? (
              <p
                role="alert"
                className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive"
              >
                {erro}
              </p>
            ) : null}

            <Button type="submit" className="w-full" disabled={enviando}>
              {enviando ? 'Entrando...' : 'Entrar'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
