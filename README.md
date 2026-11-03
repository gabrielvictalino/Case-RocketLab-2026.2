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

## Camada Gold de faturas

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
