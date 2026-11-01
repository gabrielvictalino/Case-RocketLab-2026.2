# Frontend — V-Energy Grid 360

Portal web em React 19, TypeScript (strict), Vite 7, Tailwind CSS 4, shadcn/ui,
React Router 7 e TanStack Query 5.

## Requisitos

- Node.js 24 (`.nvmrc`) e `npm`
- Workspace Python (`uv sync --package backend` na raiz) apenas quando precisar
  regenerar o schema OpenAPI (`npm run gen:api`)

## Comandos

Execute a partir de `frontend/`:

```bash
npm ci                 # instala dependências a partir do package-lock.json
npm run dev            # servidor de desenvolvimento (http://localhost:5173)
npm run lint           # ESLint
npm run typecheck      # tsc --noEmit nos tsconfigs de app e node
npm test               # suíte de testes com Vitest
npm run build          # tsc -b && vite build (saída em dist/)
npm run preview        # pré-visualiza o build de produção
```

Na CI (`.github/workflows/ci.yml`), o job `frontend` usa a versão do Node.js de
`.nvmrc` e executa `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` e
`npm run build`.

## Proxy de desenvolvimento e Nginx (produção/Compose)

No `npm run dev`, chamadas para `/api` são redirecionadas pelo Vite para
`process.env.BACKEND_URL ?? 'http://localhost:8000'` (porta publicada em
`127.0.0.1:8000` exclusivamente pelo `docker-compose.override.yml` para
desenvolvimento).

Na subida completa via Docker Compose (`docker compose up -d`), o `infra/nginx/Dockerfile`
compila o bundle (`dist/`) em multi-stage (`node:24-alpine` → `nginx:1.28-alpine`) e o
serviço `nginx` é o único que publica porta no `docker-compose.yml` base
(`${PORTAL_PORT:-80}:80`, acessível em `http://localhost`):

- Serve a SPA com fallback `try_files $uri /index.html` (`Cache-Control: no-cache` no
  `index.html` e `immutable` por 1 ano em `/assets/`).
- Faz proxy reverso de `/api/v1/` para `http://backend:8000` propagando `X-Request-ID`,
  com `client_max_body_size 10m` e retorno `404` JSON para rotas `/api/` fora de `/api/v1/`.
- Aplica rate limit por IP: `20 req/s` (`burst=40 nodelay`) em `/api/v1/` e `2 req/s`
  (`burst=5 nodelay`, `proxy_read_timeout 120s`) em `/api/v1/assistente/` e
  `/api/v1/insights/`, respondendo `429` em JSON com cabeçalho `Retry-After: 1`.

## Cliente da API e `gen:api`

Os tipos da API ficam em `src/lib/api/schema.d.ts` (gerados pelo
`openapi-typescript` e commitados no repositório; **nunca edite à mão**). O
cliente tipado (`api`, `ErroApi`, `desembrulhar`) fica em
`src/lib/api/cliente.ts`.

Quando um schema ou rota do backend mudar, regenere os tipos sem precisar subir
Postgres ou Redis:

```bash
uv sync --package backend   # na raiz do repositório, se ainda não sincronizado
cd frontend
npm run gen:api
```

## Login e período

Em desenvolvimento (`app.seed`), os usuários de demonstração são criados com
login igual ao cargo (`diretoria`, `comercial`, `atendimento`, `perdas` e
`operacao`) e senha `Demo-Venergy-2026!`. A sessão fica em `localStorage` na
chave `venergy.sessao` e qualquer resposta `401` fora do login redireciona para
`/login` preservando a rota de retorno.

O período e o período de comparação globais ficam sincronizados na URL no
formato `?periodo=AAAA-MM..AAAA-MM&comparacao=AAAA-MM..AAAA-MM` (por padrão, os
últimos 12 meses contra os mesmos 12 meses do ano anterior, segundo os limites
de `GET /api/v1/meta/carga`) e são expostos às telas pelo hook `usePeriodo()`.
