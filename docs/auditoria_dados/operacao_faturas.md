# Operação e revisões da Silver de faturas

## Arquivos e evidência

| Arquivo | Finalidade | Revisões | Evidência Databricks |
| :--- | :--- | :--- | :--- |
| [bronze-to-silver-faturas-evidencia-2026-10-29.ipynb](../../data-engineering/bronze-to-silver-faturas-evidencia-2026-10-29.ipynb) | Anexo do autor, com código e outputs históricos preservados | `v-energy.silver` | Run All com `true`, concluído em 29/10/2026 |
| [bronze-to-silver-faturas.ipynb](../../data-engineering/bronze-to-silver-faturas.ipynb) | Cópia para futuras execuções | `v-energy.silver_revisoes` | Execuções com `false` e `true` comprovadas em 30/10/2026; arquivo operacional com outputs da execução com `true` |

O arquivo de evidência recebeu somente ajustes de apresentação e identificação após a renomeação. Código, outputs, widget e demais metadados históricos foram preservados. Nele,
o widget exportado está em `true`. A versão operacional conserva as regras
de negócio e separa o schema das revisões; os destinos definitivos continuam
em `v-energy.silver.tb_faturas` e `v-energy.silver.tb_faturas_pendentes_cadastro`.

O notebook unificado de ingestão continua em
[Landing_to_Bronze.ipynb](../../data-engineering/Landing_to_Bronze.ipynb),
com seu conteúdo preservado. Ele atende às várias fontes Bronze.

## Antes de executar

Uma execução completa com `confirmar_publicacao=true` cria revisões e substitui
as duas tabelas finais configuradas. A configuração padrão aponta para os
destinos do projeto em `v-energy.silver`. Confirme os destinos antes de iniciar;
um teste isolado precisa de configuração própria de destino. Alterar somente
`CATALOGO` também altera as referências Bronze e exige essas fontes no outro catálogo.

Configure primeiro **On widget change → Do Nothing** no painel de widgets.
Isso evita que uma mudança de valor reexecute somente as células que acessam
o widget e invalide os marcadores sem refazer as validações intermediárias.
Um widget existente pode conservar o valor `true`, mesmo que o código defina
`false` como padrão de criação.

Depois de conferir esses pontos, uma execução em `false` valida somente a
candidata e não grava schemas, revisões ou destinos. Uma publicação intencional
usa `true` e executa desde o início, em uma única execução publicadora por vez.
Em um Job, forneça o parâmetro de notebook explicitamente; este PR não cria
nem agenda um Job no workspace.

Não defina `VALIDACOES_CANDIDATA_OK`, `REVISAO_PERSISTIDA_OK` ou
`PUBLICACAO_FATURAS_OK` manualmente. Esses marcadores resultam das conferências.
Ao terminar uma publicação, preserve os outputs e volte o widget a `false`,
com **Do Nothing** já configurado. Não é preciso reexecutar para voltar o seletor.

## Schema das revisões

Na cópia operacional, `SCHEMA_SILVER = "silver"` identifica os destinos finais
e `SCHEMA_REVISOES = "silver_revisoes"` identifica as revisões. O código recusa
a configuração dos dois nomes iguais. Com `true`, cria os schemas se necessário
e usa nomes exclusivos por execução, sem sobrescrever revisões anteriores.

Exemplos de nomes futuros:

```text
v-energy.silver_revisoes.tb_faturas_revisao_<uuid>
v-energy.silver_revisoes.tb_faturas_pendentes_cadastro_revisao_<uuid>
```

As fontes são lidas em versões Delta fixadas. A conferência compara a
persistência com a candidata da mesma execução, incluindo os metadados.
O plano conserva a identidade Delta, a versão e o snapshot conferido;
mudanças detectadas nas fontes ou destinos bloqueiam a publicação.

O isolamento organiza os objetos intermediários; não limita sozinho o volume
armazenado. Este PR não implementa exclusão automática nem move as revisões
antigas de `silver`. A limpeza deve ser uma operação separada, após auditoria
e resolução de publicações parciais, com prazo de retenção acordado pela equipe.
Nenhuma revisão deve ser apagada para contornar uma validação que falhou.

## Publicação comprovada e limites

O anexo registra a execução de 29/10/2026, das 19h18min36s às 19h22min46s,
no fuso America/Fortaleza, sem erros ou `Command skipped`. As revisões dessa
rodada têm sufixo `1bb6358d020a4ca1b1148d09c87c2fc7` e foram criadas em
`v-energy.silver`, antes da separação implementada na cópia operacional.

| Destino | Versão | Faturas | Valor total |
| :--- | ---: | ---: | ---: |
| `v-energy.silver.tb_faturas` | 2 | 2.152.336 | R$ 666.482.773,76 |
| `v-energy.silver.tb_faturas_pendentes_cadastro` | 1 | 32.285 | R$ 10.192.373,82 |

As células 87 e 91 conferiram os schemas e conteúdos completos das revisões
e dos destinos; a célula 92 reconciliou 2.184.621 faturas e R$ 676.675.147,58
e registrou sucesso. Isso comprova o caminho de publicação do anexo. A execução da cópia com `silver_revisoes` foi comprovada separadamente em 30/10/2026. Não comprova execução da Gold ou de um Job integrado.

As duas substituições são transações separadas. Se uma falhar depois da outra,
preserve as revisões, os outputs e o registro `publicacoes_realizadas` para
investigar o estado antes de continuar. Não há rollback automático conjunto.

## Atualização operacional — 30/10/2026

As execuções com `false` e `true` foram conferidas no mesmo código Python da versão operacional atual. A publicação com `true` criou revisões em `silver_revisoes` e publicou `silver.tb_faturas` na versão Delta **3** e `silver.tb_faturas_pendentes_cadastro` na versão **2**. As contagens e os valores foram mantidos. Tabelas referentes a 29/10/2026 neste documento permanecem como histórico.

Consulte o [registro das novas evidências](evidencias_operacionais_faturas.md), com anexos originais, horários, hashes e limites da validação. Os anexos conservam os nomes anteriores à renomeação.
