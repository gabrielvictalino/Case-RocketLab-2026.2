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

## Proxy de desenvolvimento

No `npm run dev`, chamadas para `/api` são redirecionadas pelo Vite para
`process.env.BACKEND_URL ?? 'http://localhost:8000'` (porta publicada pelo
`docker-compose.override.yml` do backend).

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
