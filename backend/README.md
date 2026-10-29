# Backend V-Energy Grid 360

FastAPI modular, Python 3.12, SQLAlchemy assíncrono e PostgreSQL 17. O workspace
uv compartilha o lockfile entre `backend`, `importador` e `ai-agent`. O agente
tem apenas sua interface preparada e não faz chamadas a provedores.

Esta entrega inclui **amostras sintéticas** e contrato
`0.2.0-provisional`, não aprovado pelo time de dados. O importador também aceita
exportações reais que cumpram essa versão, preservando a proveniência. Consulte
[`contracts/README.md`](../contracts/README.md) e
[`docs/backend-pendencias.md`](../docs/backend-pendencias.md).

## Subir e inicializar

Requisitos: Docker com Compose v2. Comandos executados na raiz do repositório:

```bash
cp .env.example .env
docker compose up -d postgres redis
docker compose build backend
docker compose run --rm migracoes
docker compose run --rm importador --origem contracts/samples
docker compose run --rm backend python -m app.seed
docker compose up -d backend
curl http://localhost:8000/api/v1/health
```

O override de desenvolvimento publica somente em `127.0.0.1`: backend 8000,
Postgres 5432 e Redis 6379. O Compose base (`docker compose -f docker-compose.yml`)
não publica portas. O frontend e o Nginx não fazem parte desta etapa.

No ambiente gerenciado com CA própria, gere a imagem com a CA combinada do
executor e reutilize-a nos comandos seguintes:

```bash
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -f backend/Dockerfile -t venergy-backend:local .
```

Volumes persistem entre execuções de `docker compose down`. Não é necessário
remover volumes para recarregar dados. As senhas de `.env.example` são locais;
ao alterá-las depois do primeiro bootstrap, altere também as roles do banco.
Nas URLs, caracteres especiais de senha precisam de percent-encoding.

## Execução Python local

Instale uv e Python 3.12. Com Postgres e Redis do Compose ativos:

```bash
uv sync --frozen --all-packages
uv run alembic -c backend/alembic.ini upgrade head
uv run importador --origem contracts/samples
uv run python -m app.seed
uv run uvicorn app.main:app --reload --log-level info
```

`uv sync --package backend` instala o backend e o agente integrado. Para executar
também o importador e a suíte completa, use `--all-packages`.

## Bootstrap, migrações e carga

1. `infra/postgres/init.sh` passa as senhas como variáveis psql ao `init.sql`,
   executado uma única vez no volume novo. Cria roles, schemas e `operations.cargas`.
2. Alembic usa `DATABASE_URL_MIGRATIONS`, exclusivamente no serviço de migrações.
   Sua tabela de versões e todas as migrações ficam em `operations`. A revisão
   `0001` assume `cargas` já existente e cria usuários, ordens, eventos e inspeções.
   `0002` acrescenta a ordem de publicação de cargas e o schema `portal_read`.
   Alterações futuras de `cargas` devem ser migrações; não reeditar o bootstrap
   esperando que ele rode num volume existente.
3. O importador depende dessa migração, pois as views unem inspeções novas e
   históricas. Execute migrações **antes** da primeira importação. O Alembic não
   depende de tabelas analíticas, eliminando o ciclo de inicialização.
4. O importador faz COPY para staging, valida o contrato e publica numa transação:
   troca schemas, recria views como dono `importador`, remove explicitamente FKs
   internas e tabelas antigas e registra a carga. Não usa `CASCADE`. Uma dependência
   desconhecida aborta a publicação e preserva todo o estado anterior.

Cada importação ganha um UUID distinto, mesmo para o mesmo `batch_id` de origem.
O UUID é a versão da carga, também publicada na chave Redis `versao_carga`.
O PostgreSQL é a fonte de verdade: se a atualização do Redis falhar, o CLI avisa,
a carga permanece confirmada e `/meta/carga` informa sua versão correta.
Um advisory lock de sessão serializa importações até o fim da atualização Redis,
inclusive após o commit. `carregado_em` usa o relógio da publicação e
`ordem_publicacao`, uma sequência do banco, define a carga atual em `/meta/carga`.
Uma falha de Redis pode manter sua chave antiga: consumidores de cache devem obter
a versão em `operations.cargas`, usando a mesma transação da consulta analítica,
e nunca confiar só na chave Redis. O cache de endpoints ainda não foi implementado.
O staging também é
transacional e desaparece quando uma carga falha.

O downgrade remove as views de inspeções conhecidas antes de remover suas tabelas,
sem `CASCADE`. Dependências externas desconhecidas continuam bloqueando a operação.
Downgrade remove os dados operacionais das revisões revertidas; faça backup antes
de usá-lo fora de uma base de teste.

Para carregar outro diretório que siga o contrato:

```bash
uv run importador --origem /caminho/exportacao
# Em container, monte o diretório explicitamente:
docker compose run --rm -v /caminho/exportacao:/entrada:ro importador --origem /entrada
# Ou configure GOLD_EXPORT_DIR no .env e use a montagem já prevista:
GOLD_EXPORT_DIR=/caminho/exportacao docker compose run --rm importador --origem /entrada
```

Manifestos com `synthetic: false` são aceitos e registrados como dados reais.
Aprovar o contrato e homologar uma exportação real com o time de dados continuam
pendentes; a validação estrutural não aprova as regras de negócio. Nenhuma operação
acessa o Databricks. Erros de duplicidade e referência informam tabela, coluna e
chave; erros de tipo incluem também a linha do CSV.

## Login e API

O seed é explícito, idempotente e permitido somente com `APP_ENV=development`.
Cria os logins `diretoria`, `comercial`, `atendimento`, `perdas` e `operacao`,
todos com senha de demonstração **`Demo-Venergy-2026!`**. Uma nova execução não
sobrescreve senhas ou usuários existentes. Hashes usam Argon2id e a verificação
do login executa no pool de threads para preservar a responsividade da API.

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login":"perdas","senha":"Demo-Venergy-2026!"}'
# Use access_token como Bearer no Swagger ou nas chamadas HTTP seguintes.
```

JWT HS256 expira em oito horas. Usuários inativos e tokens com cargo desatualizado
são rejeitados. Só `perdas` escreve ordens; todos os cargos autenticados podem ler
os endpoints desta etapa. `/health` e `/auth/login` são públicos; o Swagger em
[`/docs`](http://localhost:8000/docs) e o OpenAPI são públicos para desenvolvimento.
Erros seguem `{"detail": ..., "code": ...}` e toda resposta inclui `X-Request-ID`.
Logs registram esse identificador, método, status e duração, sem corpos ou tokens.

Rotas implementadas:

| Rota em `/api/v1` | Comportamento |
|---|---|
| `GET /health` | Verifica PostgreSQL e Redis, retorna 503 se indisponíveis |
| `POST /auth/login` | Login JSON `{login, senha}`, retorna token |
| `GET /meta/carga` | Versão, data, limites da base e indicação de dados sintéticos |
| `GET /meta/filtros` | Municípios, bairros por município, classes e alimentadores |
| `GET /ordens-inspecao?status=&page=1&size=25` | Listagem com snapshot, máximo 100 por página |
| `POST /ordens-inspecao` | Lote `{ucs: [...]}`, criadas e rejeitadas; não aborta por UC repetida |
| `POST /ordens-inspecao/{id}/despachar` | `{inspetor: "INSP-001"}` |
| `POST /ordens-inspecao/{id}/tentativas` | `{observacao: "Imóvel fechado"}` |
| `POST /ordens-inspecao/{id}/resultado` | `{resultado, tipo_irregularidade, kwh_recuperado, data}` |
| `POST /ordens-inspecao/{id}/cancelar` | `{motivo: "..."}` |

`core/periodos.py` valida `AAAA-MM..AAAA-MM`, limites e comparação padrão no ano
anterior. `/meta/filtros` aceita `periodo` e `comparacao` para exercitar a mesma
validação que será usada nos módulos de métricas. Sem um ano anterior completo,
o período atual continua válido e o utilitário devolve comparação `None`. Módulos
de métricas devem indicar comparação indisponível. Uma comparação explícita fora
da base continua retornando 422.

Criar uma ordem congela o score, os motivos e os valores sintéticos da fila.
Transições usam bloqueio da linha e gravam eventos na mesma transação. O índice
único parcial garante uma ordem ativa por UC inclusive sob concorrência.
Tentativas sem acesso registram observação e inspetor no evento, mesmo que a ordem
volte a ficar sem atribuição. Resultado com data futura retorna 422.
Concluir gera uma inspeção nova. `portal_read.inspecoes` une históricas e novas
com a coluna `origem`. A IA usa `ai_read.inspecoes`, uma projeção independente e
explícita: alterações na view do portal não ampliam a allowlist. Ordens não referenciam `analytics`
por FK: o snapshot precisa sobreviver a uma recarga ou à retirada da UC da Gold.

## Testes e validações

```bash
uv sync --frozen --all-packages
uv run ruff check backend ai-agent importador contracts conftest.py
uv run ruff format --check backend ai-agent importador contracts conftest.py
uv run pytest -q
git diff --check
```

Docker precisa estar ativo para a suíte completa. Testcontainers cria Postgres 17
e Redis 7 temporários, executa o bootstrap, Alembic, seed e importador reais.
Não é necessário subir o Compose antes dos testes. Falta de Docker causa falha,
não um skip silencioso. Testes cobrem autenticação, cargos, períodos, amostras
reproduzíveis, manifesto, falhas na validação e na publicação, recarga preservando
`operations`, privilégios reais da IA, unicidade concorrente, transições e rollback
da auditoria. Os testes existentes do Fluxo Git também continuam rodando.

Somente testes sem containers:

```bash
uv run pytest -m 'not integration' -q
```

O workflow `Aplicação` detecta alterações em código, contratos, infraestrutura e
configuração compartilhada. Só então roda lint, formatação e a suíte do backend;
o agregador obrigatório `CI` sempre executa e aceita o skip por ausência de mudanças.
Falha ou cancelamento do detector/backend falha o agregador. `Fluxo Git` permanece independente.
Frontend, cache de endpoints, planilha de campo, métricas finais e IA completa
ficam para próximas entregas.
