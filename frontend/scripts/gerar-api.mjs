import { spawnSync } from 'node:child_process'
import { mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const frontendDir = path.resolve(__dirname, '..')
const openapiPath = path.join(frontendDir, '.openapi.json')
const schemaOutPath = path.join(frontendDir, 'src', 'lib', 'api', 'schema.d.ts')

const checkUv = spawnSync('uv', ['--version'], { stdio: 'ignore' })
if (checkUv.error || checkUv.status !== 0) {
  console.error(
    'Erro: o utilitário "uv" não foi encontrado no PATH. Instale o uv e execute "uv sync --package backend" antes de rodar "npm run gen:api".',
  )
  process.exit(1)
}

const pythonSnippet =
  'import json; from app.main import create_app; print(json.dumps(create_app().openapi(), ensure_ascii=False, indent=2))'

const exportResult = spawnSync(
  'uv',
  ['run', '--package', 'backend', 'python', '-c', pythonSnippet],
  {
    cwd: frontendDir,
    env: {
      ...process.env,
      APP_ENV: 'development',
    },
    stdio: ['ignore', 'pipe', 'inherit'],
    encoding: 'utf-8',
  },
)

if (exportResult.status !== 0 || !exportResult.stdout) {
  console.error('Erro ao exportar o schema OpenAPI do backend.')
  process.exit(exportResult.status ?? 1)
}

writeFileSync(openapiPath, exportResult.stdout, 'utf-8')
mkdirSync(path.dirname(schemaOutPath), { recursive: true })

const npxBin = process.platform === 'win32' ? 'npx.cmd' : 'npx'
const tsResult = spawnSync(
  npxBin,
  ['openapi-typescript', openapiPath, '-o', schemaOutPath],
  {
    cwd: frontendDir,
    stdio: 'inherit',
  },
)

if (tsResult.status !== 0) {
  console.error('Erro ao gerar tipos TypeScript com openapi-typescript.')
  process.exit(tsResult.status ?? 1)
}
