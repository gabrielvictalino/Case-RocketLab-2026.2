# Fluxo Git e colaboração

Baseado no PDF “06 — Fluxo de Git & Guia de Colaboração”, adaptado ao
Case RocketLab V-Energy. O provedor de CI adotado é o GitHub Actions.

## Branches e ciclo de trabalho

- `main`: módulo concluído e revisado; recebe apenas PRs da `dev` deste repositório.
- `dev`: integração do módulo; recebe PRs de branches de trabalho.
- `<tipo>/<descricao-curta>`: um tópico, em kebab-case, criado a partir de `dev`.
  Tipos: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`.
  Exemplo com issue: `feat/42-dashboard-energia`.

```bash
git checkout dev
git pull --ff-only origin dev
git checkout -b feat/42-dashboard-energia
# Trabalhe, faça commits e atualize a branch antes do review:
git fetch origin
git rebase origin/dev
git push -u origin feat/42-dashboard-energia
```

Abra o PR para `dev` e preencha o template padrão: o quê, por quê, testes e
impacto em documentação. Atualize decisões e checklists no mesmo PR.
Durante o review, responda com novos commits, sem force-push.
Após aprovação e CI verde, use squash se houver commits intermediários;
caso contrário, merge commit. Exclua apenas a branch de trabalho após o merge.

Ao concluir o módulo, abra `dev` → `main` com
`?template=modulo_para_main.md`. Revise o funcionamento ponta a ponta,
a documentação e o checklist. Prefira merge commit nesta promoção para
preservar a ancestralidade entre as branches. A `dev` é permanente.
Opcionalmente marque o módulo com uma tag como `v0.1.0`.

## Conventional Commits

Formato: `<tipo>(<escopo>): <resumo>`, com escopo opcional.
Tipos são os mesmos das branches; `!` pode indicar uma mudança incompatível.
Use escopos do projeto, como `backend`, `frontend`, `data-engineering` e `ai-agent`.
Adotamos português nos resumos, mantendo tipos e escopos sem tradução.

```text
feat(frontend): adiciona painel de consumo
fix(backend): corrige cálculo de energia
chore(ci): configura validações do repositório
```

O título do PR também segue esse formato, inclusive nas promoções:
`chore(release): conclui módulo 1`. A CI valida os commits de PRs para `dev`,
exceto commits de merge usados para atualização. Na promoção para `main`,
os commits já foram revisados na integração.

## CI e proteção

O check obrigatório `Fluxo Git` roda em todo PR para `dev` e `main`, além de
pushes nessas branches. Valida origem, nome de branch, título, commits e
whitespace do diff. Não usa filtros por caminho, evitando checks pendentes
em PRs de documentação. A origem de uma branch a partir da `dev` continua
sendo responsabilidade do autor; o nome sozinho não comprova essa origem.

Os arquivos `.github/rulesets/main.json` e `dev.json` exigem PR, uma aprovação,
resolução de conversas e o check `Fluxo Git`. Novos commits invalidam reviews.
Bloqueiam exclusão e force-push, sem exceções para administradores.
A `main` também exige atualização antes do merge. Histórico linear não é
exigido, pois o fluxo admite merge commits.

### Ativação no GitHub

Os JSONs versionados não ativam proteção automaticamente. Após integrar esta
configuração na `main`, um administrador autenticado com `gh` deve executar:

```bash
bash scripts/configurar-github.sh
```

Requer GitHub CLI, `rg` e acesso administrativo ao repositório. O script cria
`dev` a partir de `main` apenas se ela não existir, habilita merge/squash e
cria ou atualiza os rulesets por nome. Não remove outros rulesets existentes.
Cria também as labels `feat`, `fix` e `tarefa` usadas pelos formulários, caso faltem.
Não habilita exclusão automática de branches para preservar `dev`.
Confira as regras em Settings → Rules → Rulesets; disponibilidade de proteção
em repositórios privados depende do plano GitHub.

### CI da aplicação

O workflow `ci.yml` executa Ruff (lint e formatação) e pytest do workspace Python,
incluindo os testes existentes do fluxo Git. Usa Python 3.12, uv com lockfile
congelado e PostgreSQL 17/Redis 7 reais via Testcontainers. O backend roda em
todas as PRs/pushes para `dev` e `main`, sem filtros por caminho. O agregador
`CI` sempre executa e falha se o backend falhar ou não concluir com sucesso.

Os rulesets versionados exigem `Fluxo Git` e `CI`. Sua ativação continua sendo
administrativa: depois da integração/revisão, reaplique
`bash scripts/configurar-github.sh`. A implementação local do backend não altera
proteções remotas. `fluxo-git.yml` permanece independente e obrigatório.

Frontend ainda não foi implementado. Quando for introduzido, inclua seu build,
lint e testes e faça o agregador depender também desse job. Evite filtros que
deixem checks obrigatórios pendentes. Comandos locais estão no
[README do backend](../backend/README.md).

## Verificação local

Execute `python3 -m unittest discover -s tests -v` e
`bash -n scripts/configurar-github.sh`. Os testes usam um repositório temporário
e verificam eventos de PR/push, rejeição de commits e branches inválidos,
promoção somente da `dev` local e rejeição de whitespace.
