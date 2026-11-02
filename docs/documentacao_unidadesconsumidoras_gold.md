# Documentação de Arquitetura e Engenharia de Dados

**Projeto:** V-Energy Grid 360
**Domínio:** Unidades Consumidoras (UCs)
**Camada:** Gold
**Versão:** 1.0
**Data:** 23 de outubro de 2026
**Notebook:** `silver-to-gold-unidades-consumidoras`
**Depende de:** `bronze-to-silver-unidades-consumidoras-v2` (documentação Silver v2)

---

## 1. Visão Geral

A camada Gold entrega os dados de Unidades Consumidoras prontos para consumo: uma dimensão analítica por UC, agregações gerenciais e de rede, uma visão temporal de ligações e indicadores de qualidade cadastral. Todas as tabelas são derivadas da Silver persistida (nunca de DataFrames em memória) e são reconstruídas por completo a cada execução.

Princípios:

- A Gold não expõe dados pessoais em claro. Nome, CPF/CNPJ, logradouro e número não existem em nenhuma tabela Gold.
- Todas as agregações partem da dimensão, o que garante consistência entre as tabelas.
- Cada tabela é reconciliada com a Silver (a soma das unidades precisa fechar) e a validação é bloqueante.
- Valores nulos em dimensões de agrupamento são exibidos como `Nao informado`, para que nenhuma UC desapareça dos relatórios.

---

## 2. Objetos do Pipeline

| Tabela | Granularidade | Finalidade |
|---|---|---|
| `workspace.default.gold_dim_unidade_consumidora` | 1 linha por `id_uc` | Dimensão analítica, base para BI e modelos |
| `workspace.default.gold_resumo_ucs_por_municipio` | município x classe | Visão gerencial. O nome foi mantido por compatibilidade com consumidores existentes |
| `workspace.default.gold_ucs_por_alimentador` | alimentador x subgrupo tarifário x classe | Base para análises de rede (Grid 360) |
| `workspace.default.gold_evolucao_ligacoes_por_ano` | ano de ligação x classe | Novas ligações e acumulado |
| `workspace.default.gold_qualidade_cadastral` | 1 linha por métrica | Indicadores de qualidade da Silver e da quarentena |

Origens: `silver_unidades_consumidoras` e `silver_unidades_consumidoras_quarentena`.

O notebook `silver-to-gold-unidades-consumidoras` substitui o `silver-to-gold-resumo-ucs` (versão inicial, que gerava apenas o resumo por município).

---

## 3. Fluxo de Processamento

1. Leitura da Silver persistida, com verificação das 21 colunas esperadas, tabela não vazia e `id_uc` único.
2. Construção da dimensão (pseudonimização do documento, colunas derivadas de tempo e geolocalização).
3. Construção das agregações a partir da dimensão.
4. Cálculo dos indicadores de qualidade (Silver e quarentena).
5. Gravação das cinco tabelas em Delta (`overwrite` com `overwriteSchema`) e comentário de tabela.
6. Validações bloqueantes sobre as tabelas gravadas.
7. Amostras e alertas.

---

## 4. Dimensão de Unidade Consumidora

Tabela: `gold_dim_unidade_consumidora`. Uma linha por UC da Silver.

| Coluna | Tipo | Descrição |
|---|---|---|
| `id_uc` | string | Chave de negócio. Única. |
| `documento_hash` | string | SHA-256 do `cpf_cnpj` precedido de salt (64 caracteres). Permite contar e cruzar titulares sem expor o documento. |
| `tipo_documento` | string | `CPF` ou `CNPJ`. |
| `documento_dv_valido` | boolean | Dígitos verificadores conferem (herdado da Silver). |
| `municipio`, `bairro`, `uf`, `cep` | string | Padronizados na Silver. Nulos preservados na dimensão. |
| `classe`, `subgrupo_tarifario`, `alimentador`, `status` | string | Padronizados na Silver. Nulos preservados. |
| `data_ligacao` | date | Data de ligação ou NULL. |
| `ano_ligacao` | int | Ano de `data_ligacao`. |
| `anos_de_ligacao` | int | Anos completos entre `data_ligacao` e a data de execução. |
| `faixa_antiguidade` | string | `0 a 4 anos`, `5 a 9 anos`, `10 a 19 anos`, `20 anos ou mais` ou `Sem data`. |
| `latitude`, `longitude` | double | Coordenadas válidas ou NULL. |
| `tem_coordenada` | boolean | Verdadeiro quando latitude e longitude estão presentes. |
| `silver_processed_datetime` | timestamp | Linhagem: processamento Silver. |
| `gold_processed_datetime` | timestamp | Processamento Gold. |

Não fazem parte da dimensão: `nome_titular`, `cpf_cnpj`, `logradouro` e `numero`.

`anos_de_ligacao` e `faixa_antiguidade` dependem da data de execução. A dimensão é, portanto, um retrato do dia do processamento.

---

## 5. Tabelas Agregadas

### 5.1 `gold_resumo_ucs_por_municipio` (município x classe)

| Coluna | Descrição |
|---|---|
| `municipio`, `classe` | Chave. Nulos aparecem como `Nao informado`. |
| `total_unidades` | Quantidade de UCs. |
| `qtd_cpf`, `qtd_cnpj` | UCs por tipo de documento. Somam `total_unidades`. |
| `qtd_com_coordenada` | UCs com coordenada válida. |
| `pct_com_coordenada` | Percentual com duas casas decimais. |
| `gold_processed_datetime` | Processamento Gold. |

As colunas além de `municipio`, `classe` e `total_unidades` são acréscimos compatíveis com o consumo existente.

### 5.2 `gold_ucs_por_alimentador` (alimentador x subgrupo tarifário x classe)

| Coluna | Descrição |
|---|---|
| `alimentador`, `subgrupo_tarifario`, `classe` | Chave. Nulos aparecem como `Nao informado`. |
| `total_unidades` | Quantidade de UCs. |
| `qtd_municipios` | Municípios distintos atendidos (desconsidera municípios nulos). |
| `qtd_cnpj` | UCs com CNPJ. |
| `qtd_com_coordenada` | UCs com coordenada válida. |

### 5.3 `gold_evolucao_ligacoes_por_ano` (ano de ligação x classe)

| Coluna | Descrição |
|---|---|
| `ano_ligacao`, `classe` | Chave. |
| `novas_ligacoes` | UCs ligadas naquele ano, entre as UCs hoje presentes na Silver. |
| `acumulado_ligacoes` | Soma acumulada por classe, em ordem de ano. |

UCs sem `data_ligacao` ficam fora desta tabela e são contabilizadas à parte na reconciliação. O acumulado representa o crescimento da base atual, não o estoque histórico real de cada ano, pois UCs desligadas ou removidas não aparecem na Silver.

### 5.4 `gold_qualidade_cadastral`

| Coluna | Descrição |
|---|---|
| `categoria` | `silver` ou `quarentena`. |
| `metrica` | Nome do indicador. |
| `valor` | Quantidade. |
| `total_referencia` | Total usado no percentual (total de UCs da Silver). Nulo para a quarentena. |
| `percentual` | `valor / total_referencia`, com duas casas. Nulo para a quarentena. |
| `gold_processed_datetime` | Processamento Gold. |

Métricas da categoria `silver`: `total_ucs`, `sem_data_ligacao`, `sem_coordenada`, `sem_cep`, `sem_uf`, `sem_municipio`, `sem_classe`, `sem_alimentador`, `documento_dv_invalido`, `total_cnpj`. Na categoria `quarentena`, uma linha por motivo de rejeição (`motivo:<nome>`).

---

## 6. Validações Bloqueantes

Executadas sobre as tabelas gravadas. Qualquer falha interrompe o notebook.

- Dimensão: sem colunas de dados pessoais (`nome_titular`, `cpf_cnpj`, `logradouro`, `numero`), uma linha por UC da Silver, `id_uc` único e `documento_hash` preenchido com 64 caracteres.
- Resumo por município: soma de `total_unidades` igual ao total da Silver, `qtd_cpf + qtd_cnpj` igual ao total e chave única.
- Alimentador: soma de `total_unidades` igual ao total da Silver e chave única.
- Evolução: `novas_ligacoes` somadas mais UCs sem data iguais ao total da Silver, chave única e acumulado final igual à soma por classe.
- Qualidade: `total_ucs` igual ao total da Silver.

Alertas (não bloqueiam): UCs sem município exibidas como `Nao informado`, além das amostras de indicadores, municípios, alimentadores, evolução e faixas de antiguidade.

---

## 7. Segurança e LGPD

- A Gold não contém nome, CPF/CNPJ em claro, logradouro nem número.
- `documento_hash` é pseudonimização, não anonimização. O espaço de CPFs é pequeno e um hash sem salt pode ser revertido por força bruta. Por isso o notebook busca o salt no secret scope `venergy`, chave `salt_documento`. Se o secret não existir, o hash é gerado sem salt e o notebook emite aviso. Em ambiente produtivo, o secret deve ser criado antes da primeira execução, e o mesmo salt precisa ser mantido para que o hash seja comparável entre execuções.
- Município, bairro, CEP e coordenadas continuam sendo dados potencialmente identificáveis em conjunto. O acesso à dimensão deve ser controlado por permissões do Unity Catalog.

---

## 8. Operação

- Todas as tabelas são reconstruídas a cada execução, a partir da Silver integral. A execução é idempotente, exceto pelos campos dependentes do tempo (`anos_de_ligacao`, `faixa_antiguidade`, `gold_processed_datetime`).
- Ordem de execução: `bronze-to-silver-unidades-consumidoras-v2` e, em seguida, `silver-to-gold-unidades-consumidoras`. Recomenda-se um Workflow do Databricks com essa dependência.
- Se o notebook Silver não tiver sido executado na versão 2, a Gold falha na verificação de colunas (`tipo_documento`, `documento_dv_valido`, `source_file`).

---

## 9. Execução de Referência

Primeira execução no Databricks, em 29/10/2026 (todas as validações bloqueantes passaram).

| Item | Valor |
|---|---|
| UCs na Silver | 45.000 |
| Linhas na dimensão | 45.000 |
| Municípios distintos no resumo | 14 (soma de `total_unidades` = 45.000) |
| UCs com CNPJ | 6.008 (13,35%) |
| UCs sem CEP | 1.350 (3,00%) |
| UCs sem `data_ligacao` (fora da evolução) | 0 |
| UCs com `documento_dv_valido` falso | 0 |
| Faixas de antiguidade | 0 a 4 anos: 586; 5 a 9 anos: 9.110; 10 a 19 anos: 18.600; 20 anos ou mais: 16.704 |
| Data de ligação mínima e máxima na Silver | 1900-01-01 e 2026-03-20 (valores extremos sob análise, ver seção 10) |
| Salt de documento | Não utilizado: o secret `venergy/salt_documento` não existia, e o hash foi gerado sem salt |
| Linhas em `gold_resumo_ucs_por_municipio` e em `gold_ucs_por_alimentador` | a registrar |

---

## 10. Decisões e Limitações Conhecidas

1. **Sem tabela fato.** A Silver contém apenas dados cadastrais; não há consumo, faturamento nem atendimentos. Quando essas fontes existirem, elas devem gerar fatos que se relacionam com `gold_dim_unidade_consumidora` por `id_uc`.
2. **Sem histórico.** A dimensão é o retrato atual (como a Silver). Mudanças de titular, classe ou status não são rastreadas; isso exigiria SCD Tipo 2.
3. **Evolução baseada na base atual.** Ver seção 5.3.
4. **Domínios sem lista oficial.** `status`, `classe`, `subgrupo_tarifario` e `alimentador` ainda não têm lista de valores válidos; as agregações refletem o que a Silver contém.
5. **Valor `Nao informado`** é um rótulo de apresentação nas agregações. Na dimensão, os nulos são preservados.
6. **Geografia não validada contra tabelas oficiais.** Município e bairro dependem da padronização da Silver; não há conferência com a tabela de municípios do IBGE.
7. **Nome da tabela de resumo.** `gold_resumo_ucs_por_municipio` tem granularidade município x classe. O nome foi mantido para não quebrar consumidores existentes e pode ser renomeado em uma versão futura com período de transição.
8. **Datas de ligação extremas em análise.** A Silver contém a data `1900-01-01` (limite inferior da regra, compatível com uma data sentinela) e UCs isoladas entre 1904 e 1937, antes do corpo da base, que começa em 1997. Elas entram nas faixas de antiguidade e na evolução por ano até que o corte mínimo de `data_ligacao` seja definido na Silver.
