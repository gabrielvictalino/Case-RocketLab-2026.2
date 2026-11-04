# Backend V-Energy Grid 360

FastAPI modular, Python 3.12, SQLAlchemy assíncrono e PostgreSQL 17. O workspace
uv compartilha o lockfile entre `backend`, `importador` e `ai-agent`. O agente
(`venergy_ai`) roda dentro do backend e chama o provedor configurado em
`AI_PROVEDOR` e `AI_MODELO`; sem a chave do provedor, o assistente e os insights
respondem 503.

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
docker compose build backend nginx
docker compose run --rm migracoes
docker compose run --rm importador --origem contracts/samples
docker compose run --rm backend python -m app.seed
docker compose up -d
curl http://localhost/api/v1/health
```

No Compose base (`docker compose -f docker-compose.yml`), **apenas o serviço `nginx` publica porta** (`${PORTAL_PORT:-80}:80`), servindo a SPA do portal em `http://localhost` e atuando como proxy reverso para `/api/v1/` com propagação de `X-Request-ID`, `client_max_body_size 10m` e limites de taxa (`20 req/s` com `burst=40` em `/api/v1/` e `2 req/s` com `burst=5` e `proxy_read_timeout 120s` em `/api/v1/assistente/` e `/api/v1/insights/`, retornando HTTP `429` JSON com cabeçalho `Retry-After`).

O `docker-compose.override.yml` é exclusivo para desenvolvimento local e publica apenas em `127.0.0.1`: backend (`8000`), Postgres (`5432`) e Redis (`6379`), permitindo usar `npm run dev` no frontend e inspecionar banco/API diretamente no host.

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
   Também tira de `PUBLIC` o `EXECUTE` em `set_config` e na família `pg_sleep`, e o
   devolve só a `portal` e `importador`. Os advisory locks de sessão
   (`pg_advisory_lock`, `pg_try_advisory_lock` e as variantes `_shared`) voltam só
   ao `importador`, que os usa para serializar as cargas. Um volume criado antes disso
   não recebe a mudança: em dev, recrie-o com `docker compose down -v` e refaça
   migrações, carga e seed.
2. Alembic usa `DATABASE_URL_MIGRATIONS`, exclusivamente no serviço de migrações.
   Sua tabela de versões e todas as migrações ficam em `operations`. A revisão
   `0001` assume `cargas` já existente e cria usuários, ordens, eventos e inspeções.
   `0002` acrescenta a ordem de publicação de cargas e o schema `portal_read`.
   `0003` cria `agente_auditoria`, gravada e lida só pela role `portal`.
   `0004` dá ao `importador` `SELECT` em `id_uc` e `status` das ordens e, num banco
   já carregado, recria na hora a fila da IA (sem as UCs com ordem ativa) e as
   inspeções da IA (tipo de irregularidade fechado), sem esperar outra importação.
   Antes, desliga `portal_read.inspecoes` de `ai_read.inspecoes` (a `0002` a cria
   sobre a da IA quando já houve carga), para o portal seguir com o texto do operador.
   Alterações futuras de `cargas` devem ser migrações; não reeditar o bootstrap
   esperando que ele rode num volume existente.
3. O importador depende dessa migração, pois as views unem inspeções novas e
   históricas. Execute migrações **antes** da primeira importação. O Alembic não
   depende de tabelas analíticas, eliminando o ciclo de inicialização.
4. O importador faz COPY para staging, valida o contrato e publica numa transação:
   troca schemas, recria views como dono `importador`, remove explicitamente FKs
   internas e tabelas antigas e registra a carga. Não usa `CASCADE`. Uma dependência
   desconhecida aborta a publicação e preserva todo o estado anterior.
5. As views de `ai_read` são apagadas num único `DROP` e recriadas a cada carga, cada
   uma com seu `GRANT SELECT` só para `ai_read`. A IA lê só as que estão em
   `importador/views.sql`, sem nome, documento e endereço do titular, sem a descrição
   das tratativas e sem o texto livre do tipo de irregularidade (fora dos cinco tipos
   da Silver, a IA vê `OUTRO`). A `ai_read.fila_inspecao` tira as UCs com ordem ativa,
   lendo `id_uc` e `status` das ordens a cada consulta.

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
| `GET /kpis?periodo=AAAA-MM..AAAA-MM` | Oito cards com valor, comparação e variações |
| `GET /kpis/serie?periodo=AAAA-MM..AAAA-MM` | Receita e volume por competência, em ordem cronológica |
| `GET /ordens-inspecao?status=&page=1&size=25` | Listagem com snapshot, máximo 100 por página |
| `POST /ordens-inspecao` | Lote `{ucs: [...]}`, criadas e rejeitadas; não aborta por UC repetida |
| `POST /ordens-inspecao/{id}/despachar` | `{inspetor: "INSP-001"}` |
| `POST /ordens-inspecao/{id}/tentativas` | `{observacao: "Imóvel fechado"}` |
| `POST /ordens-inspecao/{id}/resultado` | `{resultado, tipo_irregularidade, kwh_recuperado, data}` |
| `POST /ordens-inspecao/{id}/cancelar` | `{motivo: "..."}` |
| `POST /assistente/perguntas` | `{pergunta, conversa_id?, contexto: {tela, periodo, comparacao, recortes}}`; resposta do agente com `id_resposta` e `conversa_id` |
| `GET /assistente/conversas/{id}` | Perguntas e respostas da conversa, lidas da auditoria; só a dona da conversa |
| `GET /assistente/respostas/{id}/auditoria` | Pergunta, contexto, SQL gerado e executado, linhas, modelo, tokens e latência; só o autor ou `diretoria` |
| `GET /insights/{tela}?periodo=AAAA-MM..AAAA-MM` | `visao-geral` ou `receita`, com os parâmetros de período e recorte da tela; 3 a 5 observações com a etiqueta da métrica e os valores que citam |

`core/periodos.py` valida `AAAA-MM..AAAA-MM`, limites e comparação padrão no ano
anterior. `/meta/filtros` aceita `periodo` e `comparacao` para exercitar a mesma
validação que será usada nos módulos de métricas. Sem um ano anterior completo,
o período atual continua válido e o utilitário devolve comparação `None`. Módulos
de métricas devem indicar comparação indisponível. Uma comparação explícita fora
da base continua retornando 422.

### KPIs da Visão Geral (#59)

As duas rotas de KPIs exigem autenticação e `periodo`; aceitam `comparacao`
opcional e os recortes `municipio`, `bairro`, `classe` e `alimentador` (combinados
por interseção). A comparação padrão é o mesmo intervalo do ano anterior.
Respostas incluem `periodo`, `comparacao` efetivamente resolvida e `carga`, com
versão, data de publicação, limites e proveniência sintética/real.

`/kpis` retorna oito campos de cards: `receita`, `receita_arrecadada`,
`volume_faturado_kwh`, `tarifa_media`, `inadimplencia`, `ucs` (subindicadores
`ativas` e `com_gd`), `continuidade` (`dec` e `fec`) e `taxa_acerto`.
Cada indicador tem `valor`, `comparacao`, `variacao` (atual menos comparação)
e `variacao_pct` (variação relativa à comparação × 100). Para taxas, `variacao`
é em pontos percentuais; `variacao_pct` continua sendo a variação relativa.
Decimais são strings JSON, preservando a precisão financeira. Isso inclui as
contagens de UC (por exemplo, `"300"`); o frontend deve convertê-las para operações
numéricas.

- Receita, arrecadação e volume somam `receita_volume_mensal`. Com recorte por
  alimentador, usam o detalhe por UC, reconciliado com o agregado na importação.
  KPIs e série usam o repositório `modules/receita/repository.py`.
- Tarifa média = receita / volume (seis casas); inadimplência =
  (receita − arrecadação) / receita × 100, conforme o [glossário](../GLOSSARY.md).
- Como o contrato não expõe status cadastral histórico, UCs ativas são as UCs
  distintas com registro mensal no período, inclusive competências sem fatura.
  UCs com GD são as ativas conectadas até a última competência selecionada,
  usando `gd_uc.data_conexao`, sem aplicar o retrato atual de `dim_uc.flag_gd`
  a períodos anteriores. Uma UC é contada uma vez no intervalo.
- DEC/FEC somam CHI/interrupções do período e dividem pelo total fixo de UCs dos
  alimentadores, contado uma única vez. Não fazem média dos índices nem somam
  o denominador a cada mês. Eventos atípicos são incluídos. Bairro e classe
  exigem o detalhe `ocorrencias_uc`: somam duração efetiva / 60 e contam somente
  ocorrências sem sobreposição, pela competência de abertura, com o cadastro
  filtrado como denominador. Consulte [a definição Gold](../docs/gold/continuidade.md).
- Taxa de acerto = inspeções confirmadas / inspeções realizadas × 100, na view
  `portal_read.inspecoes` (históricas + novas), pela data da inspeção. O último
  dia da competência final está incluído. Sem recorte, também entram inspeções
  operacionais de UCs que tenham saído do cadastro da carga atual.

Indicadores sem observação, comparação indisponível e razões com denominador
zero retornam `null`. Uma observação de valor zero continua sendo zero (por
exemplo, inspeções realizadas sem nenhuma confirmação). `/kpis/serie` retorna
`serie: [{competencia, receita, volume_faturado_kwh}]` para todos os meses do
período; lacunas ficam com valores nulos.

A rota `/receita/decomposicao` e o teste cruzado KPIs × decomposição ficam para
a #55/P20, junto com locais e grupos. Antes de publicar a rota, essa entrega deve
resolver a ambiguidade da R5 entre decompor totais filtrados e somar efeitos por
subgrão. KPIs e série são conferidos diretamente contra os CSVs da amostra nos
recortes por município e alimentador; o repositório de totais também tem seus
componentes de tarifa e bandeira conferidos contra o detalhe por UC.
As métricas usam o contrato vigente `0.3.0-provisional`; esta implementação não
homologa uma exportação real nem altera a Gold.

Criar uma ordem congela o score, os motivos e os valores sintéticos da fila.
Transições usam bloqueio da linha e gravam eventos na mesma transação. O índice
único parcial garante uma ordem ativa por UC inclusive sob concorrência.
Tentativas sem acesso registram observação e inspetor no evento, mesmo que a ordem
volte a ficar sem atribuição. Resultado com data futura retorna 422.
Concluir gera uma inspeção nova. `portal_read.inspecoes` une históricas e novas
com a coluna `origem`. A IA usa `ai_read.inspecoes`, uma projeção independente e
explícita: alterações na view do portal não ampliam a allowlist. Ordens não referenciam `analytics`
por FK: o snapshot precisa sobreviver a uma recarga ou à retirada da UC da Gold.

O assistente roda com um teto de 30 s (`ASSISTENTE_TIMEOUT_S`). Tempo esgotado,
falha do provedor e banco da IA fora do ar respondem 503 (`ASSISTENTE_TEMPO_ESGOTADO`,
`PROVEDOR_INDISPONIVEL`, `BANCO_INDISPONIVEL`). Toda pergunta fica na auditoria, também
as que falham e as que o cliente abandona no meio (`CANCELADA_PELO_CLIENTE`): o erro, o
SQL que já rodou e os tokens já gastos. Uma consulta lenta da
`ai_read` é erro da consulta, com nova tentativa e "não sei", e não o 503. A `tela`
aceita só as telas do portal, e os recortes, nomes e códigos sem aspas, quebras de
linha, `<` nem `>`: os dois chegam às instruções do modelo. A pergunta só
usa conexões do portal antes e depois do agente, para conferir o token, ler a
carga e gravar a auditoria. Enquanto o modelo responde, nenhuma conexão do portal
fica presa e as rotas das telas não disputam o pool. O agente recebe só a engine
`ai_read`.

Limites por usuário, no Redis e fail-open (se o Redis cair, vale só o limite por IP
do Nginx):

- `rl:{usuario}:assistente`: janela deslizante de 1 minuto com
  `ASSISTENTE_PERGUNTAS_POR_MINUTO` perguntas (padrão 20). A pergunta barrada não entra
  na janela.
- `cota:{usuario}:{AAAA-MM-DD}`: tokens do LLM gastos no dia, também os de perguntas
  que falharam, até `ASSISTENTE_COTA_TOKENS_DIA` (padrão 500.000). O dia vira à
  meia-noite de Recife.

Os dois respondem `429` com `Retry-After` (`LIMITE_DE_PERGUNTAS`,
`COTA_DE_TOKENS_ESGOTADA`).

Insights (`GET /insights/{tela}`): os fatos saem dos mesmos serviços da tela
(`kpis` na Visão Geral; `receita.decomposicao`, `grupos` e `locais` na Receita), numa
sessão curta do portal, e o modelo só redige. Todo número de uma observação precisa
estar nos fatos; a que cita um número de fora é descartada e, sem nenhuma válida, a
rota responde `503 INSIGHT_INDISPONIVEL`. Provedor fora do ar e tempo esgotado também
são 503 (`PROVEDOR_INDISPONIVEL`, `INSIGHT_TEMPO_ESGOTADO`). O insight fica 24 h em
`insight:{batch_id}:{tela}:{sha1(pedido)}`, e o pedido inclui os fatos: enquanto os
números da tela não mudam, ele sai do cache; uma inspeção concluída que muda a taxa de
acerto gera outro, sem invalidação manual. Só quem vai ao modelo gasta
`rl:{usuario}:insights` (`INSIGHTS_POR_MINUTO`, padrão 30) e a cota diária de tokens.
Sem Redis, o insight é gerado a cada pedido.

Follow-up: `conversa:v2:{id}` no Redis guarda a dona, e `conversa:v2:{id}:trocas`, a
lista das últimas 5 trocas (pergunta, métrica, filtros, período, SQL e o período da tela),
com TTL de 2 h renovado a cada pergunta, também nas que não gravam troca. O `v2` separa
do formato anterior (`conversa:{id}` com um JSON só): uma conversa aberta antes do deploy
segue como conversa nova. Uma troca que não se lê mais fica fora do histórico, sem
derrubar a pergunta. A troca nova entra num script Lua que confere a dona, acrescenta e corta
a lista no próprio Redis: duas perguntas ao mesmo tempo na mesma conversa guardam as duas
trocas, sem uma gravar por cima da lista que a outra leu. O agente
recebe esse estado estruturado, e não só a transcrição: "E em Olinda?" mantém a métrica
e o período da troca anterior e troca o município. Sem período na pergunta, vale o da
troca anterior, depois o da tela; se a tela mudou de período desde a troca anterior, vale
o da tela, com a comparação dela. Uma resposta sem métrica (fora do domínio) não muda o
estado. Sem Redis, a pergunta segue sem histórico; o histórico permanente fica na
auditoria e sai em `GET /assistente/conversas/{id}`.

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
Cache de endpoints, planilha de campo, demais métricas e IA completa
ficam para próximas entregas.
