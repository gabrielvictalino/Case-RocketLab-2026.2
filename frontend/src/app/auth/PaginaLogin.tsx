import { useState, type FormEvent } from 'react'
import { AlertCircle } from 'lucide-react'
import { Navigate, useNavigate, useSearchParams } from 'react-router'
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
        api.POST('/api/v1/auth/login', { body: corpo }),
      )
      salvarSessao(token, corpo.login)
      navigate(destinoRetorno, { replace: true })
    } catch (err) {
      if (err instanceof ErroApi && err.status === 401) {
        setErro('Login ou senha inválidos')
      } else if (err instanceof ErroApi) {
        setErro(err.message)
      } else {
        setErro('Não foi possível autenticar. Tente novamente.')
      }
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div
      className="ve-root"
      data-theme="light"
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--space-6)',
        background: 'var(--surface)',
        color: 'var(--ink)',
      }}
    >
      <div
        className="ve-panel"
        style={{
          width: '100%',
          maxWidth: '400px',
          padding: 'var(--space-6)',
        }}
      >
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: 'var(--space-2)',
            marginBottom: 'var(--space-5)',
          }}
        >
          <div className="ve-logo">
            <svg
              width="28"
              height="28"
              viewBox="0 0 32 32"
              aria-hidden="true"
              className="ve-logo-mark"
            >
              <rect
                x="0"
                y="0"
                width="32"
                height="32"
                rx="7"
                className="bg"
              />
              <path
                d="M7 8h5.2L16 19.4 19.8 8H25l-6.6 16h-4.8z"
                className="v"
              />
            </svg>
            <span className="ve-logo-word">
              V-<b>Energy</b> Grid 360
            </span>
          </div>
          <div>
            <h1
              style={{
                margin: '4px 0 0',
                fontSize: '20px',
                lineHeight: '26px',
                fontWeight: 600,
              }}
            >
              Acesso ao portal
            </h1>
            <p
              className="ve-muted"
              style={{
                margin: '2px 0 0',
                fontSize: '13px',
                lineHeight: '18px',
              }}
            >
              Informe suas credenciais para acessar o painel.
            </p>
          </div>
        </div>

        <form onSubmit={aoSubmeter} className="ve-stack" noValidate>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label
              htmlFor="campo-login"
              style={{
                fontSize: '12px',
                lineHeight: '16px',
                fontWeight: 500,
                color: 'var(--ink-muted)',
              }}
            >
              Login
            </label>
            <input
              id="campo-login"
              name="login"
              type="text"
              autoComplete="username"
              required
              disabled={enviando}
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              style={{
                height: 'var(--size-control)',
                padding: '0 var(--space-3)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--line-strong)',
                background: 'var(--surface-raised)',
                color: 'var(--ink)',
                font: 'inherit',
                fontSize: '14px',
              }}
            />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
            <label
              htmlFor="campo-senha"
              style={{
                fontSize: '12px',
                lineHeight: '16px',
                fontWeight: 500,
                color: 'var(--ink-muted)',
              }}
            >
              Senha
            </label>
            <input
              id="campo-senha"
              name="senha"
              type="password"
              autoComplete="current-password"
              required
              disabled={enviando}
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              style={{
                height: 'var(--size-control)',
                padding: '0 var(--space-3)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid var(--line-strong)',
                background: 'var(--surface-raised)',
                color: 'var(--ink)',
                font: 'inherit',
                fontSize: '14px',
              }}
            />
          </div>

          {erro ? (
            <p
              role="alert"
              style={{
                margin: 0,
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-2)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--critical-soft)',
                color: 'var(--critical)',
                fontSize: '13px',
                fontWeight: 500,
              }}
            >
              <AlertCircle size={16} className="ve-icon" aria-hidden="true" />
              <span>{erro}</span>
            </p>
          ) : null}

          <button
            type="submit"
            disabled={enviando}
            className="ve-btn ve-btn-primary"
            style={{
              width: '100%',
              justifyContent: 'center',
              marginTop: 'var(--space-1)',
            }}
          >
            {enviando ? 'Entrando...' : 'Entrar'}
          </button>
        </form>
      </div>
    </div>
  )
}
