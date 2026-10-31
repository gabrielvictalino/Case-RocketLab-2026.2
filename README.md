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

Build, lint e testes da aplicação devem ser definidos quando a stack for adicionada.

## Camada Gold de faturas

O [guia de execução](data-engineering/README.md) descreve o notebook PySpark,
a publicação Delta, a exportação CSV e o Job Databricks da Gold de faturas.
As regras, os grãos e as limitações das métricas estão no
[dicionário de dados](docs/gold/faturas.md). O volume usado nas análises é um
proxy de leituras utilizáveis; as fontes não comprovam kWh faturado nem parcelas
isoladas de tarifa/bandeira. A referência do status de pagamento é um parâmetro
explícito da carga. Os testes locais e a CI usam Spark com dados sintéticos.
