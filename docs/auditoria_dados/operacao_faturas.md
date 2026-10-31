# Operação e publicação da Silver de faturas

Use somente [bronze-to-silver-faturas.ipynb](../../data-engineering/bronze-to-silver-faturas.ipynb).
O arquivo versionado está sem outputs e com `confirmar_publicacao=false`.
Um widget existente no workspace pode conservar outro valor: confira-o antes
 de executar. Em Jobs, forneça o parâmetro explicitamente. Configure **On widget
change → Do Nothing**, concorrência máxima **1** e uma única identidade com
permissão de escrita nos destinos, revisões e marcador. As verificações de
estado não constituem lock contra escritores externos.

## Contratos e execução

`false` valida a candidata e o contrato dos destinos, sem gravar ou limpar tabelas.
`true` exige executar desde o início: valida, cria revisões exclusivas em
`v-energy.silver_revisoes`, confere seu conteúdo e publica os destinos em `silver`.
Mudanças de nome, tipo ou ordem das colunas de destinos existentes bloqueiam
antes das gravações. Migrações exigem procedimento separado, revisado.
`INSERT OVERWRITE` mantém o contrato e os metadados dos destinos existentes;
novos destinos usam `CREATE TABLE ... AS SELECT`. Não há substituição de tabela
existente por CTAS.

IDs da principal seguem `^FT[0-9]{9}$`. Nas pendências, são aceitos esse padrão
ou `^FTX[0-9]{7}$`, conforme os IDs da extração auditada. `FT12`, cabeçalhos e
espaços são recusados. Um futuro formato exige revisão explícita do contrato.
A classificação cadastral depende do join, nunca apenas do prefixo.

## Confirmação e consumo pela Gold

As duas tabelas finais continuam sendo escritas em transações separadas.
Só depois da conferência integral de ambas, uma transação Delta substitui
`v-energy.silver.tb_faturas_publicacao` com exatamente duas linhas:
`id_execucao`, `destino`, `fonte`, `versao_fonte`, `versao_destino`, `confirmado_em`.
Uma falha anterior mantém o marcador anterior. Na primeira carga, sua ausência
significa que nenhuma publicação foi confirmada. Não há rollback conjunto.

**A Gold deve ler o marcador uma única vez por execução e consumir as revisões
imutáveis indicadas por `fonte` e `versao_fonte`.** Ler diretamente os nomes
finais continua sujeito a publicação parcial. Exemplo de contrato do consumidor:

```python
linhas = spark.table("`v-energy`.`silver`.`tb_faturas_publicacao`").collect()
esperados = {
    "`v-energy`.`silver`.`tb_faturas`",
    "`v-energy`.`silver`.`tb_faturas_pendentes_cadastro`",
}
if (len(linhas) != 2 or {r["destino"] for r in linhas} != esperados
        or len({r["id_execucao"] for r in linhas}) != 1):
    raise ValueError("Publicação ausente ou incompleta")
fontes = {
    r["destino"]: spark.read.option("versionAsOf", r["versao_fonte"]).table(r["fonte"])
    for r in linhas
}
```

O PR não contém uma integração Gold já executada. Adote esse contrato antes
 de habilitar consumidores. Leitores iniciados antes da próxima publicação
continuam lendo seu par anterior, dentro da janela de retenção.

## Retenção

Após confirmar uma publicação, o fluxo registra em
`silver_revisoes.tb_faturas_retencao` a primeira observação de cada revisão
fora do marcador, com `nome` e `aposentada_em`. O MERGE insere somente nomes
novos, preservando o prazo em publicações seguintes e após reinícios.
**A idade de criação (`createdAt`) não autoriza exclusão.** Uma revisão criada
há 30 dias e retirada agora do marcador permanece por pelo menos mais sete dias.
O registro pode ser posterior à retirada, o que apenas estende a proteção.

A limpeza remove somente revisões com `aposentada_em` anterior ao limite de
sete dias e que não estejam no marcador atual. Só nomes
`tb_faturas[_pendentes_cadastro]_revisao_<uuid>` com UUID hexadecimal de
32 caracteres são elegíveis. Ausência ou estrutura inválida do marcador
impede a limpeza. Falha ao registrar a aposentadoria impede a exclusão nessa
execução; falha de limpeza é informada sem desfazer a publicação confirmada.
Em `false` não há escrita no registro nem limpeza. O pipeline nunca reutiliza
UUIDs; reativar manualmente revisões antigas não é uma operação suportada.
O registro de retenção é mantido como metadado de auditoria, mesmo após o DROP.

Não há shallow clone: as revisões devem ter seus próprios arquivos, sem
vínculo com arquivos de uma fonte sujeita a DROP/VACUUM. A remoção de tabelas
segue a recuperação/retenção do catálogo; não equivale a liberação imediata
de todos os bytes. Não execute leitores por sete dias ou mais; não reduza o
VACUUM abaixo dessa janela. Revisões de execuções falhas ficam disponíveis
por pelo menos sete dias após sua primeira observação fora do marcador,
e são recolhidas após um sucesso futuro. Se o Job
ficar sem sucessos, a limpeza não roda: investigue e execute manutenção após
resolver a falha, preservando as fontes do marcador. Revisões antigas no schema
`silver` exigem limpeza manual após auditoria e não são tocadas pelo fluxo.

## Evidências e validação pendente

A evidência de 29/10 fica em HTML estático em
`docs/auditoria_dados/evidencias/faturas-2026-10-29/`, sem cópia `.ipynb`
executável. Os exports de 30/10 (false e true) são referenciados pelo commit
histórico, sem duplicação no estado atual. Links e hashes estão no
[registro de evidências](evidencias_operacionais_faturas.md).

As execuções de 29 e 30/10 comprovam o código anterior, não o protocolo novo.
As correções de 31/10 foram verificadas localmente com testes de falhas simuladas.
Antes de produção, execute em catálogo de teste com `false`, depois `true`,
simule falha na segunda escrita e confirme que a Gold mantém o par do marcador
anterior. Confira também permissões de CREATE, INSERT, MERGE e DROP e preservação dos
metadados. Nenhuma tabela Databricks foi alterada por esta revisão.

## Revisão de retenção e CI — 31/10/2026

As proteções passaram a integrar o agregador `CI`, incluindo alterações em
`data-engineering/` no detector. Os testes localizam células por marcadores
estáveis e usam Java Matcher.find para validar os padrões rlike com `\z`.
Treze testes locais passaram, incluindo duas publicações próximas após uma
revisão antiga e tentativa de finalizar publicação após falha da segunda escrita.
A nova retenção ainda precisa ser exercitada no Databricks; o export de execução
com `true` anterior a esta correção não valida o registro de aposentadoria.
