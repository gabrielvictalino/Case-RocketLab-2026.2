# Documentação de Arquitetura e Engenharia de Dados — Silver de Unidades Consumidoras

**Projeto:** V-Energy Grid 360
**Domínio:** Unidades Consumidoras (UCs)
**Camada:** Silver
**Versão:** 2.1 (Unificada em `` `v-energy` ``)
**Data:** 31 de outubro de 2026
**Notebook:** `data-engineering/bronze_to_silver/bronze-to-silver-unidades-consumidoras.ipynb`

---

## 1. Visão Geral

A camada Silver é a fonte única de verdade para os dados cadastrais das Unidades Consumidoras. Ela recebe os dados brutos da Bronze unificada, rejeita registros inválidos (com rastreabilidade em tabela de quarentena), garante uma linha por `id_uc` no padrão `^UC\d{6}$`, corrige o encoding UTF-8/Latin-1 dos bairros, padroniza domínios conforme o contrato do portal (`dim_uc` e `GLOSSARY.md`), aplica tipagem forte e publica uma tabela Delta pronta para consumo analítico.

Princípios adotados:

- **Leitura fixada (`VERSION AS OF`):** a versão Delta de `` `v-energy`.bronze.tb_unidades_consumidoras `` e a constante `DATA_EXECUCAO` (`current_date()`) são capturadas uma única vez no início do job.
- **Nenhum registro some em silêncio:** tudo que sai da Bronze termina na Silver, na quarentena ou na contagem de duplicatas descartadas, e a soma é conferida a cada execução (reconciliação de volumes).
- **Validação bloqueante antes e depois da escrita com `RESTORE`:** todas as regras críticas e a reconciliação de volumes rodam sobre `df_silver` e `df_quarentena` **antes** do `overwrite` e novamente sobre as tabelas gravadas. Se a gravação ou a conferência pós-escrita falhar, `restaurar_tabela` reverte ambas as tabelas (`RESTORE TABLE ... TO VERSION AS OF` ou `DROP TABLE IF EXISTS` na primeira carga).

---

## 2. Objetos do Pipeline

| Objeto | Tabela / Notebook | Descrição |
|---|---|---|
| Bronze | `` `v-energy`.bronze.tb_unidades_consumidoras `` | Ingestão da Bronze unificada (`Landing_to_Bronze.ipynb`, PR #14), com 46.461 linhas em texto. |
| Silver | `` `v-energy`.silver.tb_unidades_consumidoras `` | Uma linha por `id_uc` (45.000 UCs válidas), higienizada e tipada. |
| Quarentena | `` `v-energy`.silver.tb_unidades_consumidoras_quarentena `` | Registros rejeitados (201 linhas: 1 cabeçalho repetido + 200 UCs de teste), com colunas originais da Bronze, motivo e timestamp. |

---

## 3. Fluxo de Processamento

1. **Leitura da Bronze (`VERSION AS OF`)** e verificação de que as 18 colunas esperadas existem.
2. **Normalização mínima das chaves** (`id_uc` em caixa alta e sem espaços nas bordas; `nome_titular` sem espaços repetidos) apenas para avaliar regras. As colunas originais permanecem intactas até a etapa de padronização.
3. **Rejeição pré-deduplicação** (seção 4): lixo, cabeçalhos repetidos, dados de teste e nulos em campos obrigatórios vão para a quarentena.
4. **Tipagem da data de ligação** antes da deduplicação, com restrição de faixa `[1900-01-01, DATA_EXECUCAO]`.
5. **Deduplicação determinística** por `id_uc` (seção 5).
6. **Validação estrutural de documentos** (seção 6): documentos inválidos vão para a quarentena.
7. **Padronização e tipagem** das colunas (seção 7), incluindo correção de mojibake UTF-8/Latin-1 nos 59 bairros e preservação das grafias canônicas com acentos (`Jaboatão dos Guararapes`, `Poder Público`).
8. **Validação bloqueante e reconciliação de volumes em memória** (antes da escrita).
9. **Gravação Delta protegida por `RESTORE`** e **revalidação sobre as tabelas gravadas**, seguida da aplicação de constraints.
10. **Perfilamento e alertas** (não bloqueantes).

---

## 4. Regras de Rejeição Pré-Deduplicação

Todas as regras são null-safe. Em PySpark, uma comparação com `NULL` não retorna verdadeiro nem falso e o `filter` descartaria a linha silenciosamente; por isso nulos são tratados explicitamente e enviados à quarentena.

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

Partição: `id_uc` normalizado.

Ordenação (primeiro critério que diferenciar as linhas):

1. `ingestion_datetime` decrescente: versão física mais recente.
2. `data_ligacao` (já tipada como data válida) decrescente, nulos por último.
3. `source_file` decrescente, nulos por último.
4. Hash SHA-256 do conteúdo de negócio, decrescente. Este é o desempate final e torna a escolha reproduzível mesmo quando todos os critérios anteriores empatam.

---

## 6. Validação Estrutural de Documentos

Após a deduplicação, o `cpf_cnpj` é reduzido apenas aos dígitos e avaliado. Documentos que falham vão para a quarentena com os dados originais.

| Motivo | Condição |
|---|---|
| `documento_ausente` | Sem nenhum dígito (inclui vazio, nulo, `-`) |
| `documento_tamanho_invalido` | Mais de 14 dígitos |
| `documento_incompleto` | Menos de 9 dígitos (parâmetro `MIN_DIGITOS_DOCUMENTO`) |
| `documento_sentinela_repetido` | Todos os dígitos iguais (por exemplo, `00000000000`) |

Documentos aprovados são padronizados assim: até 11 dígitos recebem `lpad` com zeros até 11 (CPF); de 12 a 14 dígitos recebem `lpad` até 14 (CNPJ). As colunas derivadas são:

- `tipo_documento`: `CPF` (11 dígitos) ou `CNPJ` (14 dígitos).
- `documento_dv_valido`: verdadeiro quando os dígitos verificadores (módulo 11) conferem. Esta coluna é informativa e **não rejeita** registros, porque bases sintéticas ou anonimizadas costumam falhar no dígito verificador e a rejeição em massa esconderia o restante dos problemas.

---

## 7. Padronização e Tratamento de Domínios

| Coluna | Regra |
|---|---|
| `id_uc` | Trim e caixa alta, validado no padrão `^UC\d{6}$`. |
| `nome_titular` | Trim e colapso de espaços repetidos. Caixa original preservada. |
| `cpf_cnpj` | Somente dígitos, `lpad` conforme seção 6. |
| `logradouro` | Trim e colapso de espaços. Acentos e caixa preservados. |
| `numero` | Trim. |
| `bairro`, `municipio` | Trim, colapso de espaços e correção de sequências UTF-8 lidas como Latin-1 (`corrigir_mojibake`, ex.: `Jardim JordÃ£o` $\rightarrow$ `Jardim Jordão`, `BrasÃ­lia Teimosa` $\rightarrow$ `Brasília Teimosa`), reduzindo as 331 grafias brutas para os 272 bairros reais e preservando a grafia canônica dos 14 municípios (`Jaboatão dos Guararapes`, `São Lourenço da Mata`, `Cabo de Santo Agostinho`, `Ilha de Itamaracá`, etc.). |
| `uf` | Caixa alta; remoção de pontos e espaços (`P.E.` vira `PE`); `PERNAMBUCO` vira `PE`; qualquer valor fora das 27 siglas oficiais vira NULL. |
| `cep` | Somente dígitos; exatamente 8; valores sentinela (`99991231`, `00000000`) e sequências de dígitos repetidos viram NULL. |
| `classe` | Mapeada para os 5 valores canônicos do contrato `dim_uc`: `Residencial`, `Comercial`, `Industrial`, `Rural` e `Poder Público`. |
| `subgrupo_tarifario`, `alimentador`, `status` | Trim, colapso de espaços e caixa alta. |
| `data_ligacao` | Convertida com `try_cast` para `DATE` (formato `yyyy-MM-dd`). Valores fora de `1900-01-01` até `DATA_EXECUCAO` (sentinelas e datas futuras) viram NULL. |
| `latitude`, `longitude` | Vírgula decimal aceita; conversão com `try_cast` para `DOUBLE`. O par é anulado (`NULL`/`NULL`) se qualquer coordenada estiver fora da caixa do Brasil (latitude -34 a 6, longitude -74 a -28) ou não for numérica. |

---

## 8. Quarentena

A tabela `` `v-energy`.silver.tb_unidades_consumidoras_quarentena `` contém todas as colunas originais da Bronze, mais:

- `motivo_rejeicao`: um dos motivos das seções 4 e 6.
- `quarentena_datetime`: momento do processamento.

---

## 9. Reconciliação de Volumes

A cada execução, a função `validar_uc_silver` imprime e valida a identidade antes e depois da gravação:

```text
Bronze = rejeitados pré-dedup + duplicatas descartadas + rejeitados de documento + Silver
```

Verificação cruzada: o número de `id_uc` distintos válidos deve ser igual a `Silver + rejeitados de documento`.

Volumetria da base unificada (`` `v-energy`.bronze.tb_unidades_consumidoras ``):

| Item | Valor |
|---|---|
| Registros na Bronze | 46.461 |
| Rejeitados pré-dedup (`cabecalho_repetido`: 1, `dado_de_teste_id_uc`: 200) | 201 |
| Duplicatas descartadas (`dedup` por `id_uc`) | 1.260 |
| Rejeitados de documento | 0 |
| **Registros na Silver** | **45.000** |

---

## 10. Dicionário de Dados da Silver

| Coluna | Tipo | Nulável | Descrição |
|---|---|---|---|
| `id_uc` | string | Não | Chave de negócio da UC (`^UC\d{6}$`). Única. |
| `cpf_cnpj` | string | Não | 11 (CPF) ou 14 (CNPJ) dígitos. |
| `tipo_documento` | string | Não | `CPF` ou `CNPJ`. |
| `documento_dv_valido` | boolean | Não | Dígitos verificadores conferem. Informativo. |
| `nome_titular` | string | Não | Nome ou razão social. |
| `logradouro` | string | Sim | Logradouro. |
| `numero` | string | Sim | Número do endereço (texto, pode conter `S/N`). |
| `bairro` | string | Sim | Bairro padronizado e com encoding UTF-8 corrigido (272 bairros). |
| `municipio` | string | Sim | Município padronizado com acentuação canônica (14 municípios). |
| `uf` | string | Sim | Sigla oficial (`PE`) ou NULL. |
| `cep` | string | Sim | 8 dígitos ou NULL. |
| `classe` | string | Não | `Residencial`, `Comercial`, `Industrial`, `Rural` ou `Poder Público`. |
| `subgrupo_tarifario` | string | Sim | Caixa alta (`B1`, `B2`, `B3`, `A4`). |
| `alimentador` | string | Sim | Caixa alta (`ALM-<MUN>-<NNN>`). |
| `data_ligacao` | date | Sim | Data de ligação ou NULL se fora da faixa. |
| `status` | string | Sim | Caixa alta (`ATIVA`). |
| `latitude` | double | Sim | NULL se o par estiver inválido. |
| `longitude` | double | Sim | NULL se o par estiver inválido. |
| `ingestion_datetime` | timestamp | Sim | Momento em que o registro pousou na Bronze. |
| `source_file` | string | Sim | Arquivo de origem do registro (herdado da Bronze). |
| `silver_processed_datetime` | timestamp | Não | Momento do processamento Silver. |

---

## 11. Qualidade de Dados

As validações bloqueantes são executadas sobre `df_silver` e `df_quarentena` **antes** do `overwrite` e novamente sobre as tabelas gravadas:

- Reconciliação de volumes fechando (seção 9) e motivos de quarentena conhecidos.
- Silver não vazia, `id_uc` único e 100% no padrão `^UC\d{6}$`.
- Zero nulos em `id_uc`, `cpf_cnpj`, `nome_titular`, `classe` e `bairro`.
- `cpf_cnpj` somente com 11 ou 14 dígitos e `tipo_documento` coerente com o tamanho.
- `cep` somente com 8 dígitos e fora da lista de sentinelas.
- `uf` somente com siglas oficiais ou NULL.
- `classe` dentro dos 5 valores canônicos do contrato (`Residencial`, `Comercial`, `Industrial`, `Rural`, `Poder Público`).
- `bairro` sem sequências de encoding corrompido (`Ã`).
- Nenhum `id_uc` iniciado por `TESTE`.
