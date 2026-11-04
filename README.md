# Case RocketLab 2026.2 — V-Energy

Consulte o [fluxo Git e guia de colaboração](docs/fluxo-git.md) antes de contribuir.

- Branches de trabalho: `<tipo>/<descricao-curta>` a partir de `dev`.
- Integração: PR para `dev`; promoção de módulo: `dev` → `main`.
- Commits e títulos de PR: Conventional Commits com resumos em português.
- CI: check **Fluxo Git**, com validação do processo e whitespace.

A ativação administrativa das proteções é descrita no guia. Após integrar a
configuração na `main`, execute `bash scripts/configurar-github.sh` com GitHub CLI
autenticado como administrador. Os JSONs em `.github/rulesets/` não ativam regras
por conta própria.

Backend, importador, contratos sintéticos e infraestrutura local estão descritos
em [backend/README.md](backend/README.md). As pendências para a Gold real estão em
[docs/backend-pendencias.md](docs/backend-pendencias.md).

Comandos de desenvolvimento, testes, proxy e geração do cliente OpenAPI do portal
web estão em [frontend/README.md](frontend/README.md).

## Dados

O [dicionário de dados da Gold](docs/gold/decisoes_silver_to_gold.md) reúne as
12 tabelas do contrato e as saídas analíticas por domínio, com notebook produtor,
grão, fórmulas e decisões de limpeza que afetam os indicadores. O índice distingue
as entregas implementadas das pendências da Gold de perdas (#124).
Os layouts de exportação estão em [contracts/README.md](contracts/README.md);
a auditoria das fontes está em [docs/overview_dados/README.md](docs/overview_dados/README.md).

### Camada Gold de faturas

O [guia de execução](data-engineering/README.md) descreve o notebook PySpark,
a publicação Delta, a exportação CSV e o Job Databricks da Gold de faturas.
As regras, os grãos e as limitações das métricas estão no
[dicionário de dados](docs/gold/faturas.md). O resumo auxiliar usa o volume das
leituras utilizáveis; as tabelas comerciais usam o consumo analítico associado
às faturas, incluindo estimativas com método e proveniência e grupos temporais.
A integração com `0.3.0-provisional` deriva tarifa base por subgrupo tarifário ×
competência e usa adicionais de bandeira fixos do case, conforme decisão
6587742059 da #67. Esses valores não comprovam kWh do sistema comercial nem
tarifa homologada. A decomposição da receita segue a R5 do contrato no consumidor.
A referência do status de pagamento é um parâmetro explícito da carga.
A [matriz de aderência](docs/gold/aderencia-faturas-0.3.md) identifica os bloqueios.
Os testes locais e o job Gold no agregador `CI` usam Spark com dados sintéticos.

## Inteligência artificial

A IA aparece de duas formas no portal: o painel **Pergunte aos dados**, em todas as telas,
que responde em português com base no banco, e os **insights** da Visão Geral e da
Receita, que comentam os números da tela sem que o usuário pergunte. As duas vivem no
pacote [`ai-agent/`](ai-agent/) (`venergy_ai`), importado pelo backend FastAPI, e não num
serviço à parte ([ADR 0001](docs/adr/0001-agente-integrado-ao-backend.md)). Framework:
PydanticAI. Modelo: Gemini 3.1 Flash-Lite pela API do Google, ou qualquer modelo do
OpenRouter, escolhido por configuração.

### Como uma pergunta é respondida

1. **Plano.** O modelo recebe a pergunta, o contexto da tela (período, comparação,
   recortes) e a camada semântica (views, colunas com unidade e domínio, regras de
   métrica, vocabulário do dia a dia e limites da base). Ele devolve um plano tipado:
   métrica, filtros, período e um SQL, ou "fora do domínio" ou "sem dado", com o motivo.
2. **Guarda de SQL.** O SQL do modelo nunca vai direto ao banco. A guarda analisa a árvore
   sintática (sqlglot), só aceita um `SELECT` sobre as views de `ai_read`, impõe
   `LIMIT 1000` e devolve o SQL regenerado, que é o que roda.
3. **Execução.** Pela role `ai_read`, só leitura, numa transação encerrada com `ROLLBACK`.
4. **No máximo uma nova tentativa.** Se a guarda ou o banco recusam o SQL, o modelo recebe
   o motivo e corrige uma vez. Se falhar de novo, a resposta é "não sei".
5. **Redação.** Uma segunda chamada escreve o texto a partir das linhas (até 50).
6. **Conferência dos números.** Todo número do texto precisa sair das linhas. Um número
   sem lastro transforma a resposta em "não sei", com o motivo.
7. **Auditoria.** A pergunta, o contexto, o SQL gerado e o executado, as linhas, o
   modelo, os tokens e a latência ficam em `operations.agente_auditoria`, gravada pela
   role do portal, também quando a pergunta falha. No painel, o bloco "Como cheguei a
   esta resposta" mostra o SQL e a tabela.

Os insights não geram SQL: o backend calcula os fatos com os mesmos serviços da tela, o
modelo só redige de 3 a 5 observações, e cada número precisa estar nos fatos, na unidade
e na métrica que a frase nomeia. Uma observação com número de fora é descartada; com
menos de 3 válidas, o bloco fica indisponível.

### Decisões

| Decisão | Escolha | Por quê |
|---|---|---|
| Quem conduz o fluxo | O código, com duas chamadas ao modelo (plano e redação) | O número de tentativas é fixo e cada passo é testável com o modelo simulado |
| Como o modelo conhece os dados | Camada semântica no prompt (`venergy_ai/semantica/`), sem RAG | São 11 views; o catálogo cabe no contexto e é testado contra o contrato e contra o banco |
| Contas | Só no SQL | Permite conferir cada número da resposta contra as linhas |
| "Hoje" | A competência mais recente da carga | A base termina numa competência fixa; "último ano" são os 12 meses até ela |
| "Não sei" | Zero linhas, erro depois da nova tentativa, fora do domínio, dado fora do catálogo, número sem lastro | Condição da Diretora de Tecnologia: dado inventado é pior que nenhum |
| Follow-up | Estado estruturado das últimas 5 trocas (métrica, filtros, período, SQL) no Redis, por 2 h | "E em Olinda?" herda a métrica e o período sem reenviar a transcrição |
| Segurança | Camadas que não dependem de o modelo obedecer | Ver [docs/seguranca-ia.md](docs/seguranca-ia.md) |

### Requisitos do case (5.2.3)

| Requisito | Onde |
|---|---|
| Perguntar em português sobre consumo, faturamento, interrupções e atendimento | `venergy_ai/agente.py`, rota `POST /api/v1/assistente/perguntas` |
| Entender "conta de luz", "falta de luz" e afins | `venergy_ai/semantica/vocabulario.py`; "falta de luz" pode ser a interrupção na rede ou a reclamação, e a resposta diz qual usou |
| Auditar como a IA chegou à resposta | `GET /api/v1/assistente/respostas/{id}/auditoria` (autor ou diretoria) e o bloco do painel |
| Insights nas telas | `GET /api/v1/insights/{tela}`, na Visão Geral e na Receita |
| Agente dentro do portal | `frontend/src/features/assistente/` |
| Não alterar dados nem sair do papel | [docs/seguranca-ia.md](docs/seguranca-ia.md) e `backend/tests/test_seguranca_ia.py` |
| Follow-up (diferencial) | `backend/app/modules/assistente/conversas.py` |
| Medir a qualidade (diferencial) | [ai-agent/evals/](ai-agent/evals/README.md) e o workflow "Avaliação do agente" |

### Como rodar

No `.env` (ver `.env.example`): `GEMINI_API_KEY` (ou `AI_PROVEDOR=openrouter` com
`OPENROUTER_API_KEY`) e, se quiser outro modelo, `AI_MODELO`. Sem a chave, o portal sobe
normalmente, e o assistente e os insights respondem `503`. Os limites ficam em
`ASSISTENTE_PERGUNTAS_POR_MINUTO`, `ASSISTENTE_COTA_TOKENS_DIA`, `INSIGHTS_POR_MINUTO` e
`ASSISTENTE_TIMEOUT_S` (30 s). As rotas estão no [README do backend](backend/README.md).

```bash
uv run pytest ai-agent
```

Esses testes usam o modelo simulado e rodam no CI obrigatório. A avaliação com o modelo
real fica fora dele, porque depende da chave e da cota do provedor:

```bash
GEMINI_API_KEY=... uv run pytest ai-agent/evals
```

O resultado da última rodada está em [docs/avaliacao-agente.md](docs/avaliacao-agente.md).

## Suposições

- Na Visão Geral, a variação de tarifa média e de UCs é neutra, pois seu sentido favorável depende do contexto.
- As séries de comparação são alinhadas pela posição das competências nos períodos; valores excedentes são descartados e competências sem correspondente permanecem vazias.
- O "hoje" do agente e dos insights é a competência mais recente da carga publicada, e não a data do relógio.
- Sem período na pergunta, o agente usa o da última troca da conversa (se a tela não mudou de período desde ela), depois o da tela e, por fim, os 12 meses até a competência mais recente. A resposta sempre declara o período usado.
- Conta atrasada é a fatura em aberto com vencimento antes da data de referência do manifesto da carga; conta em aberto é a fatura `ABERTA`, vencida ou não.
- A fila de inspeção que o agente consulta é a mesma do portal: a fila da Gold sem as UCs com ordem aberta ou em campo.
- Os testes do agente e a avaliação rodam sobre a amostra sintética de `contracts/samples`. As perguntas de avaliação não têm número escrito à mão: o esperado sai de uma consulta de referência, e vale igual para a Gold real.
