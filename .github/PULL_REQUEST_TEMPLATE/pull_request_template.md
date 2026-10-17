<!--
PR padrão: <tipo>/* → dev
Se este PR é de dev → main (módulo concluído), use o template de módulo:
adicione ?template=modulo_para_main.md na URL de criação do PR.
-->

## O quê
<!-- O que isso muda, em uma ou duas frases? -->

## Por quê
<!-- Qual problema ou item de checklist isso endereça? -->

Closes #

## Como foi testado?
<!-- Marque o que se aplica e descreva brevemente. -->
- [ ] Testes unitários
- [ ] Testes de integração
- [ ] Passos manuais:
  1.
  2.
- [ ] Não se aplica (ex.: apenas documentação)

## Toca alguma decisão registrada na documentação?
- [ ] Não
- [ ] Sim → documento(s) atualizado(s) neste PR:
  <!-- ex.: docs/dicionario-de-dados.md, README.md -->

## Tipo de mudança
- [ ] `feat` — nova feature ou capacidade
- [ ] `fix` — correção de bug
- [ ] `docs` — apenas documentação
- [ ] `refactor` — sem mudança de comportamento
- [ ] `test` — apenas testes
- [ ] `chore` — ferramental, dependências, config, CI
- [ ] `style` — apenas formatação

## Módulo afetado
- [ ] data-engineering
- [ ] backend
- [ ] frontend
- [ ] ai-agent
- [ ] docs

## Evidências (opcional)
<!-- Prints, GIFs, saída de queries, print do Workflow no Databricks, etc. -->

## Checklist do autor
- [ ] A branch foi criada a partir da `dev` e segue `<tipo>/<descricao-curta>`
- [ ] O PR tem como destino a `dev` (não a `main`)
- [ ] A branch está atualizada com a `dev` (rebase ou merge)
- [ ] Commits seguem Conventional Commits
- [ ] Build, testes e lint passam localmente / CI verde
- [ ] Sem credenciais, tokens ou dados sensíveis no diff
- [ ] Sem force-push durante o review

## Notas para o revisor
<!-- Pontos de atenção, trade-offs, partes que merecem olhar mais cuidadoso. -->

<!--
Merge: Squash-merge apenas se houver vários commits menores ("wip");
caso contrário, Merge Commit tradicional. Apague a branch após o merge.
-->