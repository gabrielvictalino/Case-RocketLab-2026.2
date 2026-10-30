# Camada Silver: `medidores`

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/bronze_to_silver/bronze-to-silver-medidores.ipynb` |
| **Entrada** | `` `v-energy`.bronze.tb_medidores `` (51.812 linhas, todas as colunas em texto) |
| **Saída** | `` `v-energy`.silver.tb_medidores `` (51.299 linhas, tipada e padronizada) |
| **Grão** | Uma linha por medidor (`id_medidor` único), ativos e retirados |
| **Depende de** | Bronze unificada (`Landing_to_Bronze.ipynb`, PR #14) |
| **Usada por** | Gold (visão 360 da UC, fila de inspeção, diagnóstico de receita) e cruzamentos com a Silver de leituras (tecnologia do medidor e datas de troca) |
| **Auditoria de origem** | `docs/auditoria_dados/auditoria_medidores.md` |

---

## 1. Resumo: o que muda da Bronze para a Silver

| | Bronze | Silver |
| :--- | :--- | :--- |
| Linhas | 51.812 | **51.299** (−513 duplicatas exatas) |
| `tipo` | 10 grafias | **3 valores**: `ELETRONICO`, `ELETROMECANICO`, `SMART` |
| `modelo` | 81 variações (espaços nas pontas) | **9 modelos** |
| Datas | texto em 4 formatos, mais a sentinela `9999-12-31` | **`DATE`**; `data_retirada` nula enquanto o medidor está ativo |
| Medidores ativos por UC | 445 UCs com 2 ativos (efeito das duplicatas) | **exatamente 1** em todas as 45.000 UCs |
| Trocas de medidor | implícitas (só dá para ver cruzando linhas) | **`id_medidor_anterior` e `tipo_anterior`** nas 6.299 trocas |

---

## 2. Regras de transformação

As regras são aplicadas na ordem abaixo. Cada uma resolve um achado da auditoria.

### 2.1. Padronização de texto (achados M3 e M4)
* **`id_medidor`, `id_uc`, `modelo`, `status`:** `trim` e maiúsculas. Isso resolve os 3.109 modelos com espaço (`"  EL-3000 "` → `EL-3000`).
* **`tipo`:** maiúsculas → remove acentos → remove espaços e hífens → remove o sufixo `METER`. Resultado, em medidores únicos:

| Grafias na Bronze | Silver | Medidores |
| :--- | :--- | :---: |
| `ELETRONICO` (23.685), `Eletronico` (1.350), `eletrônico` (1.304) | `ELETRONICO` | 26.339 |
| `ELETROMECANICO` (14.703), `ELETRO-MECANICO` (601), `Eletromecanico` (598), `eletromecânico` (591) | `ELETROMECANICO` | 16.493 |
| `SMART` (7.614), `smart meter` (439), `Smart` (414) | `SMART` | 8.467 |

> **Por que uma regra e não uma tabela de-para:** uma variação nova numa carga futura (ex.: `ELETRÔNICO` ou `Smart Meter`) cai no valor certo sem mudar o código. Se algo não couber no domínio (ex.: `DIGITAL`), a validação barra a carga e mostra a linha.
>
> **Por que só espaços e hífens:** são os únicos separadores que aparecem nas grafias da Bronze. Dígitos e outros símbolos continuam no valor, então `ELETRONICO 2` vira `ELETRONICO2` e é barrado como fora do domínio, em vez de ser aceito como `ELETRONICO` (apontado na review do PR #22).

### 2.2. Conversão de datas (achados M5 e M6)
O formato é escolhido **pelo padrão do próprio valor**, nunca por tentativa e erro:

| Padrão do valor | Formato | Linhas na Bronze | Exemplo Bronze → Silver |
| :--- | :--- | :---: | :--- |
| `9999-99-99` | `yyyy-MM-dd` | 48.084 | `2011-12-20` → 2011-12-20 |
| `99-99-9999` | **`MM-dd-yyyy`** | 1.263 | `04-07-1999` → **1999-04-07** |
| `99/99/9999` | `dd/MM/yyyy` | 1.249 | `12/01/2019` → 2019-01-12 |
| `99.99.9999` | `dd.MM.yyyy` | 1.216 | `20.04.2007` → 2007-04-20 |

* **Hífen = padrão americano.** Nas 1.263 datas com hífen o 1º campo nunca passa de 12, enquanto o 2º passa em 761 (prova na seção 3.1 da auditoria). Ler como dia-mês corromperia 469 datas sem nenhum erro. É o mesmo padrão das datas de leituras.
* **Sentinela:** `9999-12-31` e campo vazio viram nulo **antes** da conversão. Sem isso, o ano 9999 entraria como data válida.
* **Data impossível** (ex.: `30/02/2020`) ou formato desconhecido vira nulo, **sem quebrar a execução**, e é barrada pela validação, que mostra a linha.
* As mesmas regras valem para `data_instalacao`, `data_retirada` e `data_ultima_manutencao`. A última está vazia hoje, mas, se uma extração futura trouxer valores, eles serão convertidos e validados.

### 2.3. Remoção de duplicatas (achado M1)
`dropDuplicates` sobre as 8 colunas de negócio, **depois** da padronização. Assim, duas linhas que só diferem por espaço ou formato de data também contam como a mesma. Resultado: **513 linhas removidas**, todas idênticas já no texto da Bronze.

Nas 3 datas, a comparação usa a data convertida ou, **se ela não converteu, o texto original**. Sem isso, um `''` e um `30/02/2025` no mesmo medidor virariam nulo os dois, contariam como duplicata, e o `dropDuplicates` manteria um deles ao acaso: a mesma Bronze poderia passar numa execução e ser barrada na seguinte. Com o texto na comparação, as duas linhas ficam, e a carga é sempre barrada (id repetido e data não convertida). Linhas que entram no mesmo grupo têm as mesmas colunas gravadas, então a escolha do `dropDuplicates` não muda a Silver (apontado na review do PR #22).

Se aparecer o mesmo `id_medidor` com conteúdo **diferente**, a carga é barrada (regra "id_medidor repetido"). Escolher uma das versões é decisão de negócio, não algo para a Silver fazer sozinha.

### 2.4. Enriquecimento: medidor anterior da UC (achado 4.1)
Os medidores de cada UC são ordenados por data de instalação, e cada um recebe o medidor anterior (`id_medidor_anterior`) e a tecnologia dele (`tipo_anterior`). Na extração atual, isso marca as **6.299 trocas** da campanha de set/2025 a mar/2026:

| Tecnologia substituída | Trocas | Tecnologia nova |
| :--- | :---: | :--- |
| `ELETROMECANICO` | 5.661 | `SMART` |
| `ELETRONICO` | 601 | `SMART` |
| `SMART` | 37 | `SMART` |

Em 100% das trocas, o novo medidor foi instalado no mesmo dia da retirada do anterior (regra de aviso "troca com lacuna" = 0).

**Empate na data de instalação:** se um medidor foi instalado e retirado no mesmo dia em que o seguinte foi instalado, os dois têm a mesma `data_instalacao`. O desempate é `data_retirada` com nulos por último: o retirado vem antes e o `ATIVO` fica por último. Sem isso, a ordem cairia no `id_medidor` (ex.: `MD500100` ativo antes de `MD500900` retirado), a troca sairia invertida e a regra abaixo barraria uma carga válida (apontado na review do PR #22).

A validação também exige que o medidor anterior esteja `RETIRADO`. Se uma carga trouxer o `ATIVO` com data de instalação anterior à do retirado (datas trocadas na origem), a ordenação inverteria a troca, gravando o retirado como se tivesse substituído o ativo. Nesse caso a carga para.

> **Por que na Silver:** é uma derivação dentro da própria tabela, sem depender de outra fonte, e deixa simples as perguntas da Gold sobre a campanha ("o consumo mudou depois da troca para smart?"), que importam para o diagnóstico de receita e para a fila de inspeção.

---

## 3. Validações (gate de qualidade)

Antes de gravar, o notebook confere 15 regras numa única passada pelos dados:
* **crítica:** qualquer violação **interrompe a carga antes do `overwrite`**. A Silver anterior continua intacta, e o notebook mostra até 20 linhas que violam a regra.
* **aviso:** aparece na tabela de resultados, mas não bloqueia a carga.

**Mesmos dados na validação e na escrita:** o notebook lê a Bronze por uma versão fixa (`VERSION AS OF`, a última no início da execução). Validação e escrita são ações separadas do Spark, e cada uma relê a Bronze. Sem a versão fixa, uma recarga da Bronze entre as duas faria o `overwrite` gravar linhas que não foram validadas. O `cache()` resolveria também o custo de recalcular, mas o Serverless não aceita `cache()`/`persist()` (apontado na review do PR #22).

**"Hoje"** é a data atual em `America/Recife` (`FUSO_LOCAL`), o fuso das datas da origem. A sessão do Databricks costuma estar em UTC, 3 horas à frente, e das 21h à meia-noite já estaria no dia seguinte.

| Regra | Nível | Por que existe | Hoje |
| :--- | :---: | :--- | :---: |
| `id_medidor` repetido após remover duplicatas exatas | crítica | Garante a chave da tabela | 0 |
| `id_medidor`/`id_uc` fora do padrão `MD…`/`UC…` + dígitos | crítica | Ids malformados quebram os cruzamentos | 0 |
| `modelo` fora do padrão `AA-999` | crítica | Detecta lixo ou coluna deslocada | 0 |
| `tipo` fora do domínio | crítica | Gold e portal agrupam por tipo | 0 |
| `status` fora do domínio | crítica | Idem | 0 |
| `data_instalacao` vazia ou não convertida | crítica | Formato novo ou data impossível | 0 |
| `data_retirada` informada mas não convertida | crítica | Idem, sem confundir com a sentinela | 0 |
| `data_ultima_manutencao` informada mas não convertida | crítica | Idem, para cargas futuras | 0 |
| `status` incoerente com `data_retirada` | crítica | `RETIRADO` sem data ou `ATIVO` com data (ex.: sentinela em outro formato) | 0 |
| Retirada anterior à instalação | crítica | Datas trocadas | 0 |
| Data no futuro (instalação, retirada ou manutenção) | crítica | Erro de digitação de ano (ex.: retirada em 2052) | 0 |
| Manutenção antes da instalação ou depois da retirada | crítica | Datas trocadas; quebraria "medidor ativo na data X" na Gold | 0 |
| UC sem exatamente 1 medidor `ATIVO` | crítica | Regra do negócio confirmada na auditoria | 0 |
| Medidor anterior não está `RETIRADO` (troca invertida) | crítica | O `ATIVO` precisa ser o último instalado da UC; senão `id_medidor_anterior` sai ao contrário | 0 |
| Troca com lacuna (instalação ≠ retirada do anterior) | aviso | UC sem medidor entre uma troca e outra | 0 |

---

## 4. Dicionário de dados: `` `v-energy`.silver.tb_medidores ``

| Coluna | Tipo | Nulo? | Descrição | Exemplo |
| :--- | :--- | :---: | :--- | :--- |
| `id_medidor` | STRING | não | Identificador do medidor (chave) | `MD500015` |
| `id_uc` | STRING | não | UC onde o medidor está ou esteve instalado | `UC100015` |
| `modelo` | STRING | não | Modelo, sem espaços | `EM-1200` |
| `tipo` | STRING | não | `ELETRONICO`, `ELETROMECANICO` ou `SMART` | `ELETROMECANICO` |
| `status` | STRING | não | `ATIVO` ou `RETIRADO` | `RETIRADO` |
| `data_instalacao` | DATE | não | Data de instalação na UC | 2019-01-12 |
| `data_retirada` | DATE | sim | Data de retirada; nula enquanto `ATIVO` | 2025-10-24 |
| `data_ultima_manutencao` | DATE | sim | Última manutenção (vazia na extração atual) | — |
| `id_medidor_anterior` | STRING | sim | Medidor que este substituiu na UC; nulo se for o primeiro | `MD500015` (no medidor novo da UC100015) |
| `tipo_anterior` | STRING | sim | Tecnologia do medidor substituído | `ELETROMECANICO` |
| `source_file` | STRING | não | Arquivo de origem na landing | `medidores.csv` |
| `ingestion_datetime` | TIMESTAMP | não | Momento da carga na Bronze | — |
| `silver_datetime` | TIMESTAMP | não | Momento da carga na Silver | — |

As descrições também estão gravadas como comentários das colunas no Unity Catalog (Catalog Explorer → aba *Columns*).

---

## 5. Decisões e alternativas

| Decisão | Alternativa descartada | Motivo |
| :--- | :--- | :--- |
| Manter os medidores `RETIRADO` | Guardar só os ativos | As leituras antigas apontam para eles, e a troca é informação de negócio |
| Remover duplicatas **depois** da padronização, com o texto original das datas que não convertem | Remover antes, sobre o texto bruto | Pega também duplicatas que só diferem por espaço ou formato de data, sem juntar uma data inválida com uma vazia |
| Ler a Bronze por versão fixa (`VERSION AS OF`) | `cache()`/`persist()` do `df_tratado` | Garante que a escrita grava o que foi validado; o Serverless não aceita cache |
| Formato de data escolhido pelo padrão do valor | Tentar vários formatos em sequência | Tentativa e erro aceitaria `04-07-1999` como 4 de julho |
| Manter `data_ultima_manutencao` (vazia) | Remover a coluna | Mantém o schema estável e valida a coluna se ela vier preenchida no futuro |
| Validação **antes** do `overwrite` | Validar depois de gravar | Uma carga reprovada nunca substitui a Silver boa |
| Domínios e formatos na célula de configuração | Valores espalhados no código | Uma mudança de regra fica num lugar só e é revisável |
| Silver sem dependência do cadastro | Cruzar com `unidades_consumidoras` aqui | O cadastro já está na Bronze unificada (PR #14), mas a conversão de `data_ligacao` e as datas implausíveis são tratadas na Silver do cadastro (PR #24). Os cruzamentos estão na seção 9 |
| Carga completa com `overwrite` | `merge` incremental | Extração única: reexecutar dá o mesmo resultado, e o Delta guarda as versões anteriores |

---

## 6. Como executar no Databricks

### 6.1. Pré-requisito
A Bronze precisa estar carregada. Confira num SQL Editor ou numa célula `%sql`:
```sql
SELECT COUNT(*) FROM `v-energy`.bronze.tb_medidores;  -- esperado: 51812
```
Se a tabela não existir, rode antes a Bronze unificada, `data-engineering/Landing_to_Bronze.ipynb` (PR #14).

### 6.2. Rodar o notebook
1. **Workspace → (sua pasta) → ⋮ → Import → File** e escolha `bronze-to-silver-medidores.ipynb`. Se o repositório estiver conectado como *Git folder*, basta abrir o arquivo.
2. No topo do notebook, **Connect → Serverless**.
3. **Run all**. O schema `` `v-energy`.silver `` é criado na primeira execução.

### 6.3. O que conferir
* **Leitura:** `` `v-energy`.bronze.tb_medidores (versão N): 51812 linhas ``, com a versão da Bronze usada na carga.
* **Tabela de validação:** 15 regras com `violacoes = 0` e `status = OK`.
* **Linha de resumo:** `Bronze: 51812 linhas | Silver: 51299 linhas | duplicatas removidas: 513`.
* **Confirmação final:** `` OK: 51299 medidores carregados em `v-energy`.silver.tb_medidores ``.
* **Evidências:** as grafias de `tipo` convergindo para 3 valores, um exemplo de cada formato de data convertido, a visão por status e tipo, e as trocas por mês.
* **No Catalog Explorer:** `v-energy` → `silver` → `tb_medidores`. As abas *Columns* (comentários), *Sample Data* e *History* (uma versão por carga).

### 6.4. Se a validação falhar
A mensagem lista cada regra crítica violada e a quantidade de linhas, e logo acima aparecem até 20 exemplos. A Silver anterior **não** foi alterada.

| Regra que falhou | Causa provável | O que fazer |
| :--- | :--- | :--- |
| `data_* não convertida` | Formato de data novo na origem | Ver o exemplo e, se for um formato legítimo, incluí-lo em `FORMATOS_DATA` |
| `tipo`/`status` fora do domínio | Categoria nova na origem | Confirmar com o negócio e incluir em `TIPOS_VALIDOS`/`STATUS_VALIDOS` |
| `id_medidor repetido` | Mesmo medidor com dados diferentes | Decidir com o negócio qual versão vale (não há escolha automática) |
| UC sem exatamente 1 `ATIVO` | Troca registrada pela metade | Investigar a UC na Bronze |
| `status incoerente com data_retirada` | Sentinela nova (ex.: `31/12/9999`) | Incluir a sentinela em `SENTINELAS_DATA` |
| `medidor anterior não está RETIRADO` | `ATIVO` com instalação anterior à do retirado (datas trocadas na origem) | Corrigir a data na origem; a Silver não escolhe qual data vale |
| `data no futuro` / `manutenção antes da instalação…` | Erro de digitação de ano ou datas trocadas | Corrigir a data na origem |

### 6.5. No Workflow (Job)
Esta tarefa depende apenas da Bronze de medidores:
```text
landing_to_bronze ──► bronze_to_silver_medidores ──► (Gold)
```
A Silver de leituras (PR #18) lê a Bronze de medidores, e não esta Silver, então não há ordem obrigatória entre as duas Silvers.

No Databricks: **Jobs & Pipelines → Create → Job**. Adicione uma tarefa *Notebook* por notebook e marque **Depends on** conforme o desenho acima. O notebook não tem parâmetros. Se a validação falhar, a tarefa fica vermelha e as tarefas seguintes não rodam.

---

## 7. Como usar

```sql
-- Medidor instalado hoje em cada UC (visão 360 do atendimento)
SELECT id_uc, id_medidor, modelo, tipo, data_instalacao
FROM `v-energy`.silver.tb_medidores
WHERE status = 'ATIVO';

-- Campanha de troca: UCs que trocaram de tecnologia e quando
SELECT id_uc, id_medidor_anterior, tipo_anterior, id_medidor, tipo, data_instalacao AS data_troca
FROM `v-energy`.silver.tb_medidores
WHERE id_medidor_anterior IS NOT NULL;

-- Leituras com a tecnologia do medidor que as registrou (ex.: consumo antes e depois da troca para smart)
SELECT l.id_uc, l.mes_referencia, l.consumo_kwh, m.tipo AS tipo_medidor
FROM `v-energy`.silver.tb_leituras l
JOIN `v-energy`.silver.tb_medidores m USING (id_medidor);
```

---

## 8. Testes realizados

O notebook foi executado sem modificações num Spark 4.0.1 + Delta 4.0.0 local (ANSI ligado), em cadeia com o notebook da Bronze. O resultado foi comparado com um cálculo independente feito em Python puro sobre o CSV:
* contagens, distribuição de `tipo` e `status`, os 9 modelos, as datas mínima e máxima, as 6.299 trocas com o tipo anterior e as datas de exemplo (inclusive `04-07-1999` → 1999-04-07) bateram 100%;
* a reexecução produz o mesmo resultado e só uma versão Delta nova;
* **6 defeitos injetados na Bronze** foram barrados pela regra certa, com a Silver intacta:
  * data impossível `30/02/2020`;
  * tipo novo `DIGITAL`;
  * mesmo id com conteúdo diferente;
  * segundo medidor ativo na UC;
  * sentinela no formato `31/12/9999`;
  * medidor `ATIVO` com instalação anterior à do retirado (troca invertida, apontado na review do PR #22).
* **Cenários da segunda review do PR #22**, com a Bronze alterada e a sessão em UTC, como no Serverless (versão anterior → versão atual):
  * `''` e `30/02/2025` na `data_retirada` do mesmo medidor: a anterior gravou, porque a duplicata escondeu a data inválida; agora a carga é barrada;
  * retirado e `ATIVO` instalados no mesmo dia, com o `ATIVO` de id menor: a anterior barrava como troca invertida; agora grava, e o `ATIVO` aponta o retirado como anterior;
  * `data_retirada` em 2052 e manutenção em 1990, antes da instalação: a anterior gravou; agora os dois são barrados;
  * `tipo` `ELETRONICO 2`: a anterior gravou como `ELETRONICO`; agora é barrado;
  * apóstrofo no comentário da tabela: a anterior quebrava no `COMMENT ON TABLE`, depois do `overwrite`; agora grava;
  * 1.000 ids em minúsculas na Bronze: a evidência 1 perdia os 1.000; agora cobre os 51.299;
  * Bronze recarregada com 50.000 linhas entre a validação e a escrita: a anterior gravou as 50.000, que não tinham sido validadas; agora grava as 51.299 validadas.
* Com a Bronze original, a versão atual dá a mesma Silver da anterior (51.299 linhas, nenhuma diferente), e os 6 defeitos acima continuam barrados.
* `ruff check` e `ruff format --check`, com a configuração do `pyproject.toml`, passam no notebook. `spark` e `display` são globais do Databricks, liberados com `# ruff: noqa: F821` na primeira célula.

**Databricks (Serverless):** o notebook também foi executado no Unity Catalog (na época em `venergy.silver`, antes da troca para os nomes da Bronze unificada), e a tabela de validação, os totais e as evidências deram os mesmos números do teste local.

---

## 9. Pendências e pontos que dependem de outras tabelas

* **Cadastro (`unidades_consumidoras`):** a Bronze do cadastro já está carregada pela Bronze unificada (PR #14), e conferi nela que as 45.000 UCs dos medidores existem no cadastro (100%). Falta conferir que nenhuma instalação é anterior à `data_ligacao`: isso depende da Silver do cadastro (PR #24), que trata as UCs repetidas e as 90 UCs com `data_ligacao` implausível (ex.: `1903-01-01`). Essas datas são problema do cadastro, não desta tabela.
* **Leituras:** a Silver de leituras (PR #18) usa a Bronze de medidores para descartar os clones `LTX`. O resultado seria o mesmo com esta tabela, porque os `id_medidor` são idênticos. Para análises que comparam datas de leitura com datas de troca, prefira esta Silver, com as datas já convertidas.
