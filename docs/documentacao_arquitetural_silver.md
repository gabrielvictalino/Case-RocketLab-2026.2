# Documentação de Arquitetura e Engenharia de Dados

**Projeto:** V-Energy Grid 360
**Domínio:** Unidades Consumidoras (UCs)
**Camada:** Silver
**Versão:** 2.0
**Data:** 23 de outubro de 2026
**Notebooks:** `bronze-to-silver-unidades-consumidoras` e `silver-to-gold-resumo-ucs`

---

## 1. Visão Geral

A camada Silver é a fonte única de verdade para os dados cadastrais das Unidades Consumidoras. Ela recebe os dados brutos da Bronze, rejeita registros inválidos (com rastreabilidade), garante uma linha por `id_uc`, padroniza domínios, aplica tipagem forte e publica uma tabela Delta pronta para consumo analítico e de machine learning.

Princípios adotados na versão 2:

- Nenhum registro some em silêncio: tudo que sai da Bronze termina na Silver, na quarentena ou na contagem de duplicatas descartadas, e a soma é conferida a cada execução (reconciliação de volumes).
- Toda validação é executada sobre as tabelas gravadas, não sobre DataFrames em memória.
- Validações estruturais são bloqueantes (o notebook falha); validações de perfil são alertas.
- A Gold deixou de ser construída dentro do notebook Silver e passou a ler a Silver persistida em um notebook próprio.

---

## 2. Objetos do Pipeline

| Objeto | Tabela / Notebook | Descrição |
|---|---|---|
| Bronze | `workspace.default.bronze_unidades_consumidoras` | Ingestão em modo append, sem tratamento. Contém duplicatas, cabeçalhos repetidos e dados de teste. |
| Silver | `workspace.default.silver_unidades_consumidoras` | Uma linha por `id_uc`, higienizada e tipada. |
| Quarentena | `workspace.default.silver_unidades_consumidoras_quarentena` | Registros rejeitados, com colunas originais da Bronze, motivo e timestamp. |
| Gold | `workspace.default.gold_resumo_ucs_por_municipio` | Contagem de UCs por município e classe (notebook separado). O nome foi mantido por compatibilidade, apesar de a granularidade ser município x classe. |

---

## 3. Fluxo de Processamento

1. **Leitura da Bronze** e verificação de que as 18 colunas esperadas existem.
2. **Normalização mínima das chaves** (`id_uc` em caixa alta e sem espaços nas bordas; `nome_titular` sem espaços repetidos) apenas para avaliar regras. As colunas originais permanecem intactas até a etapa de padronização.
3. **Rejeição pré-deduplicação** (seção 4): lixo, cabeçalhos repetidos, dados de teste e nulos em campos obrigatórios vão para a quarentena.
4. **Tipagem da data de ligação** antes da deduplicação, com restrição de faixa.
5. **Deduplicação determinística** por `id_uc` (seção 5).
6. **Validação estrutural de documentos** (seção 6): documentos inválidos vão para a quarentena.
7. **Padronização e tipagem** das colunas (seção 7).
8. **Gravação** da Silver e da quarentena em Delta (`overwrite`), aplicação de constraints.
9. **Reconciliação de volumes** e validações bloqueantes sobre as tabelas gravadas.
10. **Perfilamento e alertas** (não bloqueantes).

---

## 4. Regras de Rejeição Pré-Deduplicação

Todas as regras são null-safe. Em PySpark, uma comparação com NULL não retorna verdadeiro nem falso e o `filter` descartaria a linha silenciosamente; por isso nulos são tratados explicitamente e enviados à quarentena.

A primeira regra que casar define o motivo.

| Ordem | Motivo | Condição |
|---|---|---|
| 1 | `id_uc_nulo` | `id_uc` nulo ou vazio (após trim) |
| 2 | `cabecalho_repetido` | `id_uc` igual a `ID_UC` (linha de cabeçalho no meio do arquivo) |
| 3 | `dado_de_teste_id_uc` | `id_uc` começando com `TESTE` (sem diferenciar maiúsculas de minúsculas, pois a chave é normalizada para caixa alta) |
| 4 | `nome_titular_nulo` | `nome_titular` nulo ou vazio |
| 5 | `dado_de_teste_titular` | `nome_titular` igual a `a` ou `teste` (sem diferenciar maiúsculas de minúsculas, após trim) |

---

## 5. Deduplicação Determinística

A Bronze opera em modo append e o arquivo de origem pode ser ingerido mais de uma vez. Além disso, o sistema de origem pode enviar a mesma chave repetida.

Partição: `id_uc` normalizado.

Ordenação (primeiro critério que diferenciar as linhas):

1. `ingestion_datetime` decrescente: versão física mais recente.
2. `data_ligacao` (já tipada como data válida) decrescente, nulos por último.
3. `source_file` decrescente, nulos por último.
4. Hash SHA-256 do conteúdo de negócio, decrescente. Este é o desempate final e torna a escolha reproduzível mesmo quando todos os critérios anteriores empatam.

Pontos de atenção:

- A data usada na ordenação é a data tipada e restrita à faixa válida. Sem isso, uma data sentinela como `9999-12-31` venceria o desempate indevidamente.
- A deduplicação descarta versões antigas por design. Essas linhas não vão para a quarentena; elas aparecem na reconciliação como "duplicatas descartadas".

---

## 6. Validação Estrutural de Documentos

Após a deduplicação, o `cpf_cnpj` é reduzido apenas aos dígitos e avaliado. Documentos que falham vão para a quarentena com os dados originais.

| Motivo | Condição |
|---|---|
| `documento_ausente` | Sem nenhum dígito (inclui vazio, nulo, `-`) |
| `documento_tamanho_invalido` | Mais de 14 dígitos |
| `documento_incompleto` | Menos de 9 dígitos (parâmetro `MIN_DIGITOS_DOCUMENTO`) |
| `documento_sentinela_repetido` | Todos os dígitos iguais (por exemplo, `00000000000`) |

Na versão 1, um documento vazio virava `00000000000` pelo `lpad`, produzindo um CPF falso que passava no teste de tamanho. Esse caso agora é rejeitado.

Documentos aprovados são padronizados assim: até 11 dígitos recebem `lpad` com zeros até 11 (CPF); de 12 a 14 dígitos recebem `lpad` até 14 (CNPJ). As colunas derivadas são:

- `tipo_documento`: `CPF` (11 dígitos) ou `CNPJ` (14 dígitos).
- `documento_dv_valido`: verdadeiro quando os dígitos verificadores (módulo 11) conferem. Esta coluna é informativa e **não rejeita** registros, porque bases sintéticas ou anonimizadas costumam falhar no dígito verificador e a rejeição em massa esconderia o restante dos problemas. A proporção é exibida como alerta na célula de perfilamento.

---

## 7. Padronização e Tratamento de Domínios

| Coluna | Regra |
|---|---|
| `id_uc` | Trim e caixa alta. |
| `nome_titular` | Trim e colapso de espaços repetidos. Caixa original preservada. |
| `cpf_cnpj` | Somente dígitos, `lpad` conforme seção 6. |
| `logradouro` | Trim e colapso de espaços. Acentos e caixa preservados. |
| `numero` | Trim. |
| `bairro`, `municipio` | Sem acentos, espaços colapsados e Title Case. Padronização necessária porque `municipio` é chave de agrupamento da Gold ("RECIFE", "Recife" e "recife" deixam de gerar grupos distintos). |
| `uf` | Caixa alta; remoção de pontos e espaços (`P.E.` vira `PE`); `PERNAMBUCO` vira `PE`; qualquer valor fora das 27 siglas oficiais vira NULL. |
| `cep` | Somente dígitos; exatamente 8; valores sentinela (`99991231`, `00000000`) e sequências de dígitos repetidos viram NULL. |
| `classe` | Sem acentos e Title Case (por exemplo, `Poder Público` vira `Poder Publico`). |
| `subgrupo_tarifario`, `alimentador`, `status` | Trim, colapso de espaços e caixa alta. Não há validação de domínio; os valores observados são listados na célula de perfilamento para definição futura de listas válidas. |
| `data_ligacao` | Convertida com `try_cast` para `DATE` (formato `yyyy-MM-dd`). Valores fora de `1900-01-01` até a data corrente (sentinelas e datas futuras) viram NULL. |
| `latitude`, `longitude` | Vírgula decimal aceita; conversão com `try_cast` para `DOUBLE`. O par é anulado (NULL/NULL) se qualquer coordenada estiver fora da caixa do Brasil (latitude -34 a 6, longitude -74 a -28) ou não for numérica. |

Observação sobre o CEP: o valor `9999-12-31` documentado na versão 1 como "anulado" na verdade era mantido, pois após remover os hifens resultava em `99991231`, que tem 8 dígitos. A regra de sentinelas corrige esse defeito.

O uso de `try_cast` evita falhas do job quando o modo ANSI do Databricks está ativo (que lança erro em conversões inválidas em vez de retornar NULL) e permite contabilizar o que foi anulado.

---

## 8. Quarentena

A tabela de quarentena contém todas as colunas originais da Bronze, mais:

- `motivo_rejeicao`: um dos motivos das seções 4 e 6.
- `quarentena_datetime`: momento do processamento.

A tabela é sobrescrita a cada execução, em sincronia com a Silver. Ela permite auditar exatamente o que foi excluído e por quê, e reprocessar casos corrigidos na origem.

---

## 9. Reconciliação de Volumes

A cada execução, a célula 7 imprime e valida a identidade:

```
Bronze = rejeitados pré-dedup + duplicatas descartadas + rejeitados de documento + Silver
```

Verificação cruzada: o número de `id_uc` distintos válidos deve ser igual a `Silver + rejeitados de documento`.

Execução de referência (versão 1 do pipeline):

| Item | Valor |
|---|---|
| Registros na Bronze | 92.922 |
| Registros do arquivo de origem | 46.461 |
| Observação | 92.922 é exatamente 2 x 46.461: o arquivo foi ingerido duas vezes na Bronze (append) |
| Registros na Silver | 45.000 |

A versão 1 da documentação informava 46.461 registros na Bronze e 1.461 exclusões, o que não correspondia à tabela real. O correto é 92.922 lidos e 47.922 não promovidos (duplicatas por dupla ingestão, duplicatas da origem, cabeçalhos e testes).

Execução da versão 2 (preencher após rodar o notebook no Databricks):

| Item | Valor |
|---|---|
| Registros na Bronze | a registrar |
| Rejeitados pré-dedup (por motivo) | a registrar |
| Duplicatas descartadas | a registrar |
| Rejeitados de documento (por motivo) | a registrar |
| Registros na Silver | a registrar |

---

## 10. Dicionário de Dados da Silver

| Coluna | Tipo | Nulável | Descrição |
|---|---|---|---|
| `id_uc` | string | Não | Chave de negócio da UC. Única. |
| `cpf_cnpj` | string | Não | 11 (CPF) ou 14 (CNPJ) dígitos. |
| `tipo_documento` | string | Não | `CPF` ou `CNPJ`. |
| `documento_dv_valido` | boolean | Não | Dígitos verificadores conferem. Informativo. |
| `nome_titular` | string | Não | Nome ou razão social. |
| `logradouro` | string | Sim | Logradouro. |
| `numero` | string | Sim | Número do endereço (texto, pode conter `S/N`). |
| `bairro` | string | Sim | Padronizado. |
| `municipio` | string | Sim | Padronizado. |
| `uf` | string | Sim | Sigla oficial ou NULL. |
| `cep` | string | Sim | 8 dígitos ou NULL. |
| `classe` | string | Sim | Classe de consumo padronizada. |
| `subgrupo_tarifario` | string | Sim | Caixa alta. |
| `alimentador` | string | Sim | Caixa alta. |
| `data_ligacao` | date | Sim | Data de ligação ou NULL se fora da faixa. |
| `status` | string | Sim | Caixa alta. |
| `latitude` | double | Sim | NULL se o par estiver inválido. |
| `longitude` | double | Sim | NULL se o par estiver inválido. |
| `ingestion_datetime` | timestamp | Sim | Momento em que o registro pousou na Bronze. |
| `source_file` | string | Sim | Arquivo de origem do registro (herdado da Bronze). |
| `silver_processed_datetime` | timestamp | Não | Momento do processamento Silver. |

---

## 11. Qualidade de Dados

As validações são executadas sobre as tabelas gravadas.

**Bloqueantes (o notebook falha com `assert`):**

- Reconciliação de volumes fechando (seção 9) e motivos de quarentena conhecidos.
- Silver não vazia e `id_uc` único.
- Zero nulos em `id_uc`, `cpf_cnpj` e `nome_titular`.
- `cpf_cnpj` somente com 11 ou 14 dígitos e `tipo_documento` coerente com o tamanho.
- `cep` somente com 8 dígitos e fora da lista de sentinelas.
- `uf` somente com siglas oficiais ou NULL.
- Nenhum `id_uc` iniciado por `TESTE`.

Constraints Delta aplicadas após a gravação: `NOT NULL` em `id_uc`, `cpf_cnpj` e `nome_titular`, e `CHECK` de tamanho do documento. Se não puderem ser aplicadas, o notebook emite aviso, e as validações bloqueantes continuam sendo o gate.

**Alertas (não bloqueiam):**

- Percentual de nulos nas colunas opcionais (`data_ligacao`, coordenadas, `cep`, `uf`, `classe`, `municipio` e demais).
- Distribuição de `documento_dv_valido` por tipo de documento.
- Domínios observados de `status`, `classe`, `uf` e `subgrupo_tarifario`.
- Nomes suspeitos: até 3 caracteres, sem espaço, ou com dígitos (este último critério só para CPF, pois razão social pode conter números).
- Documentos com mais de uma UC e contagem da quarentena por motivo.

Resultados observados na versão 1 (execução anterior): 45.000 UCs, 45.000 documentos distintos, 38.992 documentos de 11 dígitos e 6.008 de 14 dígitos, zero nulos nas colunas obrigatórias e zero nomes suspeitos. A relação 1:1 entre UC e documento é uma observação de perfil, não um critério de qualidade: em uma distribuidora real, um titular com várias UCs é comum, e a ausência total de repetição sugere base sintética ou amostral.

---

## 12. Linhagem e Auditoria

- `ingestion_datetime` e `source_file` são preservados da Bronze; `silver_processed_datetime` é adicionado. Isso separa o momento em que o dado pousou no data lake do momento em que foi higienizado.
- A quarentena preserva o registro original completo, o motivo e o timestamp.
- O notebook imprime a reconciliação de volumes a cada execução, permitindo registrar o histórico de execuções.

---

## 13. Segurança e LGPD

`cpf_cnpj` e `nome_titular` são dados pessoais e estão armazenados em claro na Silver e na quarentena. Recomendações para o ambiente produtivo:

- Restringir o acesso às duas tabelas por meio de permissões do Unity Catalog.
- Aplicar column masks em `cpf_cnpj` e `nome_titular` para perfis analíticos.
- Disponibilizar para consumo geral uma visão ou tabela com o documento pseudonimizado (hash) quando o valor original não for necessário.
- Definir política de retenção para a quarentena.

---

## 14. Operação e Idempotência

- A Silver e a quarentena são reconstruídas por completo a cada execução (`overwrite` com `overwriteSchema`), sempre a partir da Bronze integral. Como a deduplicação é determinística, reexecutar sem alterações na Bronze produz o mesmo resultado (exceto `silver_processed_datetime` e `quarentena_datetime`).
- `overwriteSchema` permite que mudanças de schema passem sem erro; as validações bloqueantes e as constraints servem como proteção.
- Para volumes maiores, a evolução natural é uma carga incremental com `MERGE` por `id_uc`.

---

## 15. Decisões de Projeto e Limitações Conhecidas

1. **Histórico não é mantido.** A Silver guarda apenas a versão mais recente de cada UC. Se o negócio precisar do histórico de mudança de titular, status ou classe, será necessário um modelo com histórico (SCD Tipo 2).
2. **Heurística CPF x CNPJ por tamanho.** Documentos com até 11 dígitos são tratados como CPF. Um CNPJ que perdeu três ou mais zeros à esquerda seria classificado como CPF.
3. **Dígito verificador não bloqueia.** Ver seção 6. A decisão pode ser revista quando a origem for confirmada como real.
4. **CEP com 7 dígitos não é recuperado.** Não há `lpad` de CEP, pois em Pernambuco os CEPs não começam com zero e completar poderia fabricar valores.
5. **Caixa geográfica do Brasil é ampla.** Ela elimina coordenadas zeradas e trocadas, mas não detecta pontos válidos no país e fora do estado. Um polígono ou caixa de Pernambuco é uma melhoria possível.
6. **Domínios de `status`, `classe`, `subgrupo_tarifario` e `alimentador` não têm lista oficial.** Os valores observados são exibidos para definir essas listas.
7. **Nomes de municípios não são validados contra a tabela do IBGE.**
8. **Documentos inválidos são rejeitados após a deduplicação.** Se a versão mais recente de uma UC tem documento inválido, ela vai para a quarentena e não há retorno à versão anterior.

---

## 16. Histórico de Alterações (v1 para v2)

| Tema | Versão 1 | Versão 2 |
|---|---|---|
| Filtros de lixo | Comparações que descartavam nulos em silêncio; teste e `a` sem normalização | Regras null-safe, normalizadas e com motivo, destino em quarentena |
| Dados de teste | Documentação citava CPF zerado e titular `TESTE`, mas o código não filtrava | Titular `a`/`teste` e documento sentinela são rejeitados |
| Deduplicação | Desempate por `data_ligacao` ainda como texto; empates possíveis | Data tipada e válida, `source_file` e hash como desempates finais |
| Documento | Vazio virava `00000000000` | Rejeição de ausente, incompleto, longo demais e sentinela; coluna de tipo e de dígito verificador |
| CEP | `9999-12-31` era mantido como `99991231` | Sentinelas e dígitos repetidos viram NULL |
| UF | Apenas duas variações mapeadas | Remoção de pontuação, mapeamento de `PERNAMBUCO` e validação contra as 27 UFs |
| Município e bairro | Apenas trim | Sem acentos, Title Case, espaços colapsados |
| Colunas ignoradas | `numero`, `subgrupo_tarifario`, `alimentador`, `status` com tratamento parcial ou nenhum | Todas tratadas |
| Datas e coordenadas | Conversão silenciosa, sem faixa | `try_cast`, faixa de datas e caixa do Brasil |
| Validações | `print` e `show` sobre DataFrame em memória | `assert` sobre tabelas gravadas, com alertas separados |
| Reconciliação | Contagens soltas e valor documentado incorreto (46.461) | Identidade impressa e validada a cada execução (Bronze real: 92.922) |
| Quarentena | Inexistente | Tabela dedicada com motivo |
| Gold | Dentro do notebook Silver, lendo DataFrame em memória | Notebook próprio, lendo a Silver persistida, com validação da soma |
| Governança | Sem constraints, sem comentário, sem menção a LGPD | Constraints Delta, comentário de tabela, seção de segurança |
