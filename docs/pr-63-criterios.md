# PR #63: critérios e pendências

Referência: [PR #63](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/pull/63)
e [revisão](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/pull/63#pullrequestreview-5692310355).

Este PR conjunto foi autorizado para a base inicial. A correção mantém a branch
e o histórico existentes. Novas tarefas devem usar branches com número de issue
e PRs menores conforme o backlog; o guia geral aceita a branch deste PR.
As referências abaixo indicam o escopo técnico. Fechamento ocorre pela integração
do PR e não substitui revisão humana ou critérios externos.

| Tarefa / issue | Critérios implementados e evidências | Pendências |
|---|---|---|
| P01 / #33 | Workspace uv, três membros, lockfile, Python fixado, pastas, Ruff, `.env.example`, ignores; instalação dos pacotes e build Docker | Nenhuma no escopo da issue |
| P02 / #34 | Doze contratos YAML, tipos/unidades/chaves, consumo original/analítico, grupos, manifesto e versão `0.2.0-provisional` | Revisão pelo time de dados; fórmula de decomposição e contrato aprovado; não fecha |
| P03 / #38 | Gerador determinístico, 300 UCs, dimensões e bordas; CSVs e manifesto versionados; teste de reprodução byte a byte e reconciliação por grão | Nenhuma no escopo sintético da issue |
| P04 / #39 | Postgres 17/Redis 7, persistência, healthchecks, schemas/roles/grants, portas só no override; testes reais de ACL e defaults após recarga | Nenhuma no escopo da issue |
| P05 / #40 | COPY, índices, mensagens de chave/referência com contexto, transação/rollback, recarga, carga registrada, Redis serializado; exportação externa e `synthetic: false` aceitos | Homologar exportação Gold real e regras com o time de dados; views mínimas da IA foram antecipadas; não fecha |
| P06 / #41 | Core, módulos, duas engines/factories, health, erros/logs, Alembic, Testcontainers, Dockerfile e README | Nenhuma no escopo da issue |
| P07 / #42 | Usuários e seed por cargo, JWT de 8 h, dependências de cargo/token, Argon2 em thread; testes positivos, negativos e de responsividade | Nenhuma no escopo da issue |
| P10 / #45 | Endpoints de metadados, dimensões distintas no SQL, períodos e comparação opcional no primeiro ano; testes dos endpoints e utilitário | Nenhuma no escopo da issue |
| P12 / #47 | Backend com Ruff/pytest, detector de caminhos, agregador sempre ativo, rulesets versionados, documentação | CI do frontend e reaplicação administrativa dos rulesets; não fecha |
| P16 / #51 | Tabelas operacionais, snapshot, índice único parcial, eventos, inspeções, grant ao importador e view unificada; testes de concorrência e preservação na recarga | Nenhuma no escopo da issue |
| P18 / #53 | Lote, despacho, tentativa com inspetor no evento, resultado sem data futura, cancelamento, listagem, cargos e auditoria atômica; testes de transições | Nenhuma no escopo da issue |

P11 / #46 (Nginx), frontend, métricas finais e agente completo ficam fora desta
entrega. Nenhuma issue de dados ou de CI parcial deve ser fechada como totalmente
concluída. A divisão de responsáveis do backlog é uma sugestão de organização;
o PR não altera atribuições ou aprovação dos demais integrantes.

## Atualização de uma instalação existente

1. Atualizar os arquivos e reconstruir a imagem.
2. Executar `docker compose run --rm migracoes` antes do backend/importador novos.
3. Reexportar manifestos e tarifas no contrato `0.2.0-provisional` ou usar as amostras
   regeneradas. Publicar a carga normalmente; não é necessário apagar volumes.
4. Reiniciar o backend. O consumidor do portal deve usar `portal_read.inspecoes`;
   a role da IA permanece restrita às projeções explícitas de `ai_read`.

A carga anterior permanece disponível até a publicação válida da próxima. A nova
migração ordena as publicações antigas pela data registrada; não é possível inferir
a ordem real de commits passados que já tenham horários incorretos. A primeira
publicação com o importador corrigido estabelece a nova ordem sem ambiguidade.
