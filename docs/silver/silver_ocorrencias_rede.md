# Camada Silver: `ocorrencias_rede`

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/bronze_to_silver/bronze-to-silver-ocorrencias-rede.ipynb` |
| **Entrada** | `` `v-energy`.bronze.tb_ocorrencias_rede `` (180.000 linhas, todas as colunas em texto) |
| **Saída** | `` `v-energy`.silver.tb_ocorrencias_rede `` (180.000 linhas, tipada e padronizada) |
| **Grão** | Uma linha por ocorrência (`id_ocorrencia` único). Pela definição do case, cada registro é **uma UC interrompida** |
| **Depende de** | Bronze unificada (`Landing_to_Bronze.ipynb`, PR #14) |
| **Usada por** | Gold de continuidade (DEC/FEC por alimentador ao longo do tempo) e visão 360 da UC ("a rua dele teve falta de luz?") |
| **Auditoria de origem** | `docs/auditoria_dados/auditoria_ocorrencias_rede.md` |

---

## 1. Resumo: o que muda da Bronze para a Silver

| | Bronze | Silver |
| :--- | :--- | :--- |
| Datas | texto `yyyy-MM-dd HH:mm:ss` | **`TIMESTAMP_NTZ`** (hora local, sem fuso) |
| `duracao_min` | texto; 16.200 valores com sufixo `" min"` | **inteiro** em 100% das linhas |
| `causa` | 6 causas + 4 formas de ausência (`''`, `-`, `N/A`, `NULL`) | 6 causas + **`NAO INFORMADA`** (5.400) |
| Sobreposição na mesma UC | soma direta conta **43.527 min em dobro** | `flag_sobreposicao` (330) e **`duracao_efetiva_min`**, dentro de cada mês |
| Evento de 2025-07 | misturado ao resto | **`flag_evento_atipico`** (12.836 ocorrências) |
| Colunas de apoio | — | `sigla_municipio` (14 siglas) e `ano_mes` (48 meses) |

---

## 2. Regras de transformação

### 2.1. Datas como `TIMESTAMP_NTZ` (achado 3.4)
As datas chegam num formato único e limpo. A conversão usa `try_to_timestamp`, que transforma valor inválido em nulo (barrado pela validação) em vez de quebrar a execução, e grava como **`TIMESTAMP_NTZ`**.

> **Por que sem fuso:** os horários são locais de Recife e a origem não informa fuso. Com o `TIMESTAMP` comum, o Spark interpreta o horário no fuso da sessão, e uma sessão configurada com outro fuso, ou uma exportação para outro banco, pode deslocar as horas. Com `NTZ`, `2022-07-01 16:33` é sempre `2022-07-01 16:33`. Isso foi testado trocando o fuso da sessão.

### 2.2. `duracao_min` como inteiro (achado 3.1)
A expressão `^\s*(\d+)\s*(min)?\s*$`, sem diferenciar maiúsculas, aceita `"217"`, `"217 min"` e `"217 MIN"`. Depois vem `try_cast` para inteiro. Os 16.200 valores com sufixo (1.946.610 minutos) entram corretamente. Um `cast` direto os transformaria em nulo e subestimaria o DEC em 9% das ocorrências. Qualquer outro formato (ex.: `"75 minutos"`) é barrado.

A validação confirma que a duração é **igual a `data_encerramento − data_abertura`** em 100% das linhas.

### 2.3. `causa` com ausência explícita (achado 3.2)
As 4 formas de ausência (`''`, `-`, `N/A`, `NULL`, num total de 5.400) viram **`NAO INFORMADA`**. O texto também passa por `trim`, maiúsculas e remoção de acentos, então `" n/a "` também é reconhecido.

| Bronze | Silver | Ocorrências |
| :--- | :--- | :---: |
| `-` | `NAO INFORMADA` | 1.363 |
| vazio | `NAO INFORMADA` | 1.356 |
| `N/A` | `NAO INFORMADA` | 1.341 |
| `NULL` | `NAO INFORMADA` | 1.340 |
| demais (6 causas) | iguais | 174.600 |

> **Decisão:** usei a categoria explícita em vez de `null` (a auditoria deixou a escolha para o time). Com isso, `GROUP BY causa` mostra a ausência como uma linha legível, e consultas como `WHERE causa <> 'CLIMATICA'` não perdem linhas por causa de nulo. Isso importa para o agente de IA, que escreve SQL sozinho. `NAO INFORMADA` (sem registro) continua separada de `NAO IDENTIFICADA` (causa investigada e não encontrada). Para usar `null`, basta trocar `CAUSA_NAO_INFORMADA` na configuração.

### 2.4. Interrupções sobrepostas na mesma UC (achado 4.2)
Para cada ocorrência, o notebook calcula o **maior encerramento entre as ocorrências anteriores da mesma UC abertas no mesmo mês** (`max(data_encerramento)` numa janela por UC, alimentador e `ano_mes`, ordenada por abertura). Comparar só com a ocorrência imediatamente anterior deixaria passar 2 casos.

* **`flag_sobreposicao`:** a ocorrência começou enquanto a UC já estava sem energia (330 casos, 268 em 2025-07).
* **`duracao_efetiva_min`:** minutos desta ocorrência que **ainda não** estavam cobertos (`encerramento − maior_fim_anterior`, ou zero).

Exemplo real, a `UC107537`:

| Ocorrência | Início | Fim | `duracao_min` | `flag_sobreposicao` | `duracao_efetiva_min` |
| :--- | :--- | :--- | :---: | :---: | :---: |
| `OC00121286` | 21/07 08:10 | 22/07 01:26 | 1.036 | false | 1.036 |
| `OC00125971` | 21/07 14:21 | 21/07 15:53 | 92 | true | **0** (contida na anterior) |
| `OC00122507` | 21/07 22:10 | 22/07 02:46 | 276 | true | **80** (01:26 → 02:46) |
| **Total** | | | 1.404 | | **1.116** = 08:10 → 02:46 |

Em toda a base, `SUM(duracao_min)` = 21.392.087 min e **`SUM(duracao_efetiva_min)` = 21.348.560 min**, que é a união dos intervalos de cada UC dentro de cada mês. São 43.527 min que uma soma direta contaria em dobro.

> **Por que dentro do mês:** a Gold soma por mês e escolhe se inclui o evento atípico. Se a sobreposição fosse calculada sobre toda a série da UC, uma ocorrência de outro mês, ou de um mês de evento atípico, poderia cobrir esta, e os minutos ficariam com a outra. Quando a Gold tirasse aquele mês da conta, eles sumiriam. Exemplo: uma ocorrência atípica de 31/07 a 02/08 cobriria uma normal de 01/08, que ficaria com 0 min; sem o evento, as 4 horas da normal desapareceriam do DEC de agosto. Com a janela por UC, alimentador e mês, e o flag valendo para o alimentador no mês inteiro, nenhuma janela mistura ocorrências com e sem o flag, e qualquer conjunto de meses soma certo (apontado na review do PR #23).
>
> **O custo:** uma interrupção que atravessa a virada do mês e cobre outra do mês seguinte conta nos dois meses. Na base atual é 1 caso, com 34 min (com a sobreposição sobre toda a série eram 331 casos e 43.561 min em dobro).

### 2.5. Evento atípico por alimentador e mês (achado 4.1)
O termo segue o glossário (**evento atípico**), e a coluna tem o mesmo nome do contrato da Gold de continuidade (`flag_evento_atipico`).

Para cada alimentador, o notebook conta as ocorrências de cada mês do calendário **entre o primeiro e o último mês em que ele aparece**. A grade é gerada com `sequence`, então um mês sem nenhuma ocorrência entra com zero. Um mês é de **evento atípico** quando passa de **5× a base mensal** do alimentador (`LIMIAR_EVENTO_ATIPICO`):
* **base** = mediana mensal do próprio alimentador, mas **nunca abaixo da mediana da rede** (todas as combinações alimentador × mês; hoje 28);
* com **menos de 12 meses** (`MESES_MINIMOS_SERIE`), a base é a mediana da rede.

| Alimentador | Mês | Ocorrências | Mediana do alimentador | Base | Razão |
| :--- | :---: | :---: | :---: | :---: | :---: |
| `ALM-REC-008` | 2025-07 | 6.887 | 28 | 28 | 246× |
| `ALM-SAO-004` | 2025-07 | 3.351 | 27 | 28 | 120× |
| `ALM-JAB-004` | 2025-07 | 2.598 | 27 | 28 | 93× |

Fora esses 3, nenhum mês de nenhum alimentador passa de **2,3×** a base, nem os picos difusos de 2025-11 e 2026-02. O limite de 5× separa os dois grupos com folga.

> **Por que o piso e a série mínima:** a mediana do próprio alimentador falha nas pontas (apontado na review do PR #23). Numa série curta, ela inclui o evento: com os meses [30, 6.887], a mediana é 3.458 e o evento escapa do limite; com um mês só, a mediana é o próprio mês. No outro extremo, um alimentador quase sem ocorrências tem mediana 0, e qualquer mês com 6 ou mais seria marcado. Com o piso na mediana da rede, o evento precisa ser grande também na escala da rede. Hoje os 122 alimentadores têm os 48 meses e medianas entre 25 e 29,5, então só os 3 casos de 2025-07 são marcados, como antes.

> **Por que limitar ao período do alimentador:** se um alimentador entrar ou sair no meio do período, os meses em que ele não existia entrariam com zero e puxariam a mediana dele para baixo. Hoje os 122 alimentadores aparecem nos 48 meses, então o resultado é o mesmo. O limite protege as próximas cargas (apontado na review do PR #23).

> **Por que uma regra e não a data fixa:** `WHERE ano_mes = '2025-07'` resolveria hoje, mas o case prevê cargas mensais. A regra marca sozinha o próximo evento parecido. O flag **não remove nada**: a Gold decide se calcula DEC/FEC com ou sem esses meses.

### 2.6. Colunas de apoio e duplicatas
* **`sigla_municipio`:** extraída do código do alimentador (`ALM-REC-008` → `REC`). São 14 siglas, coerentes 100% com o município do cadastro (auditoria, seção 6).
* **`ano_mes`:** mês de abertura em `yyyy-MM`, para agregações mensais.
* **Duplicatas exatas:** linhas iguais nas colunas da Bronze, removidas depois da padronização. A Bronze atual não tem nenhuma, mas a regra protege as próximas cargas. O mesmo id com conteúdo diferente bloqueia a carga.

---

## 3. Validações (gate de qualidade)

Antes de gravar, o notebook confere 12 regras críticas numa única passada pelos dados. Qualquer violação **interrompe a carga antes do `overwrite`** (a Silver anterior continua intacta), e o notebook mostra até 20 linhas que violam a regra.

**Mesmos dados na validação e na escrita:** o notebook lê a Bronze por uma versão fixa (`VERSION AS OF`, a última no início da execução). Validação e escrita são ações separadas do Spark, e cada uma relê a Bronze. Sem a versão fixa, uma recarga da Bronze entre as duas faria o `overwrite` gravar linhas que não foram validadas. O `cache()` resolveria também o custo de recalcular, mas o Serverless não aceita `cache()`/`persist()` (apontado na review do PR #23).

**"Agora"** é a hora atual em `America/Recife` (`FUSO_ORIGEM`), o mesmo fuso das datas da origem, como `TIMESTAMP_NTZ`. Comparar com `localtimestamp()` usaria o fuso da sessão, que no Serverless costuma ser UTC, 3 horas à frente, e uma abertura até 3 horas no futuro passaria.

| Regra | Por que existe | Hoje |
| :--- | :--- | :---: |
| `id_ocorrencia` repetido após remover duplicatas exatas | Garante a chave da tabela | 0 |
| `id_ocorrencia`/`id_uc` fora do padrão `OC…`/`UC…` + dígitos | Ids malformados quebram cruzamentos | 0 |
| `alimentador` fora do padrão `ALM-AAA-999` | DEC/FEC são calculados por alimentador | 0 |
| `tipo` fora do domínio (5 valores) | Categoria nova precisa de decisão | 0 |
| `causa` fora do domínio (7 valores) | Idem | 0 |
| `data_abertura` vazia ou não convertida | Formato novo ou data impossível | 0 |
| `data_encerramento` vazia ou não convertida | Idem | 0 |
| Encerramento anterior à abertura | Datas trocadas geram duração negativa | 0 |
| Abertura ou encerramento no futuro (hora de Recife) | Erro de digitação de ano | 0 |
| `duracao_min` vazia ou não convertida | Formato novo (ex.: `"75 minutos"`) | 0 |
| `duracao_min` ≠ encerramento − abertura | As duas fontes de duração precisam concordar | 0 |
| `duracao_efetiva_min` fora de [0, `duracao_min`] | Sanidade do cálculo de sobreposição | 0 |

O notebook também imprime os totais de sobreposição (330 ocorrências e 43.527 min em dobro), a mediana da rede e a lista de meses de evento atípico, com a contagem, a mediana do alimentador e a base de cada um.

---

## 4. Dicionário de dados: `` `v-energy`.silver.tb_ocorrencias_rede ``

| Coluna | Tipo | Nulo? | Descrição | Exemplo |
| :--- | :--- | :---: | :--- | :--- |
| `id_ocorrencia` | STRING | não | Identificador da ocorrência (chave). Cada ocorrência é uma UC interrompida | `OC00000010` |
| `id_uc` | STRING | não | UC interrompida | `UC107256` |
| `alimentador` | STRING | não | Alimentador de média tensão | `ALM-JAB-007` |
| `sigla_municipio` | STRING | não | Sigla do município, extraída do alimentador | `JAB` |
| `tipo` | STRING | não | `FALTA DE ENERGIA`, `FIO PARTIDO`, `OSCILACAO`, `SOBRECARGA` ou `DANO EM EQUIPAMENTO` | `FALTA DE ENERGIA` |
| `causa` | STRING | não | 6 causas ou `NAO INFORMADA` | `CLIMATICA` |
| `data_abertura` | TIMESTAMP_NTZ | não | Início da interrupção (hora local) | 2022-07-01 16:33:00 |
| `data_encerramento` | TIMESTAMP_NTZ | não | Fim da interrupção (hora local) | 2022-07-01 20:10:00 |
| `ano_mes` | STRING | não | Mês de abertura (`yyyy-MM`) | `2022-07` |
| `duracao_min` | INT | não | Duração registrada (= encerramento − abertura) | 217 |
| `duracao_efetiva_min` | INT | não | Minutos não cobertos por ocorrência anterior da mesma UC no mesmo mês. **Use `SUM` desta coluna para o tempo sem energia** | 217 |
| `flag_sobreposicao` | BOOLEAN | não | `true` se a UC já estava sem energia, por outra ocorrência aberta no mesmo mês, quando esta começou. **Para contar interrupções, use as linhas com `false`** | false |
| `flag_evento_atipico` | BOOLEAN | não | `true` se a ocorrência foi aberta num mês de evento atípico do alimentador (mais de 5× a base mensal dele) | false |
| `source_file` | STRING | não | Arquivo de origem na landing | `ocorrencias_rede.csv` |
| `ingestion_datetime` | TIMESTAMP | não | Momento da carga na Bronze | — |
| `silver_datetime` | TIMESTAMP | não | Momento da carga na Silver | — |

As descrições também estão gravadas como comentários das colunas no Unity Catalog.

---

## 5. Decisões e alternativas

| Decisão | Alternativa descartada | Motivo |
| :--- | :--- | :--- |
| `TIMESTAMP_NTZ` | `TIMESTAMP` com fuso | Horário local sem fuso na origem; evita deslocamento de horas entre sessões e exportações |
| `NAO INFORMADA` explícita | `null` | Agrupamentos legíveis e SQL sem armadilhas de nulo; separada de `NAO IDENTIFICADA` |
| Sobreposição por **maior encerramento acumulado** | Comparar com a ocorrência anterior imediata | A comparação simples perde 2 casos e deixa minutos em dobro (revisão do PR #9) |
| Sobreposição **dentro do mês** | Sobre toda a série da UC | A Gold soma meses, com ou sem o evento atípico, sem perder minutos; custa 34 min contados em dois meses na base atual |
| `duracao_efetiva_min` por linha | Tabela separada de intervalos unidos | Mantém um grão só, e `SUM`/`COUNT_IF` resolvem DEC e FEC direto |
| Evento atípico por **regra** (5× a base mensal do alimentador, com piso na mediana da rede) | Data fixa `2025-07` no código | Funciona nas próximas cargas mensais, inclusive com alimentadores novos, desativados, com série curta ou quase sem ocorrências; nada é removido |
| Validação **antes** do `overwrite` | Validar depois de gravar | Uma carga reprovada nunca substitui a Silver boa |
| Ler a Bronze por versão fixa (`VERSION AS OF`) | `cache()`/`persist()` do `df_tratado` | Garante que a escrita grava o que foi validado; o Serverless não aceita cache |
| Silver sem dependência do cadastro | Cruzar com `unidades_consumidoras` aqui | O cadastro já está na Bronze unificada (PR #14), mas as UCs repetidas e as datas implausíveis são tratadas na Silver do cadastro (PR #24). Os cruzamentos estão na seção 9 |

---

## 6. Como executar no Databricks

### 6.1. Pré-requisito
```sql
SELECT COUNT(*) FROM `v-energy`.bronze.tb_ocorrencias_rede;  -- esperado: 180000
```
Se a tabela não existir, rode antes a Bronze unificada, `data-engineering/Landing_to_Bronze.ipynb` (PR #14).

### 6.2. Rodar o notebook
1. **Workspace → (sua pasta) → ⋮ → Import → File** e escolha `bronze-to-silver-ocorrencias-rede.ipynb` (ou abra pelo *Git folder*).
2. **Connect → Serverless**.
3. **Run all**. O schema `` `v-energy`.silver `` é criado se ainda não existir.

### 6.3. O que conferir
* **Tabela de validação:** 12 regras com `violacoes = 0` e `status = OK`.
* **Resumo:** `Bronze: 180000 linhas | Silver: 180000 linhas | duplicatas removidas: 0`.
* **Leitura:** `` `v-energy`.bronze.tb_ocorrencias_rede (versão N): 180000 linhas ``, com a versão da Bronze usada na carga.
* **Totais:** `Sobrepostas: 330 | minutos somados: 21392087 | minutos efetivos: 21348560 | em dobro: 43527`, `Ocorrências em evento atípico: 12836` e `Mediana da rede (alimentador × mês): 28.0`.
* **Meses de evento atípico:** os 3 alimentadores de 2025-07, com contagem, mediana e base.
* **Confirmação final:** `` OK: 180000 ocorrências carregadas em `v-energy`.silver.tb_ocorrencias_rede ``.
* **Evidências:**
  * causa Bronze → Silver;
  * duração com e sem sufixo;
  * minutos somados × efetivos;
  * prévia do DEC/FEC por alimentador com e sem o evento atípico, em que o `ALM-REC-008` cai de 35.646 h para 2.112 h sem o evento.

### 6.4. Se a validação falhar
A mensagem lista cada regra crítica violada e a quantidade de linhas, e logo acima aparecem até 20 exemplos. A Silver anterior **não** foi alterada.

| Regra que falhou | Causa provável | O que fazer |
| :--- | :--- | :--- |
| `data_* não convertida` | Formato de data/hora novo | Ajustar `FORMATO_DATA_HORA` (ou tratar mais de um formato, como em medidores) |
| `duracao_min não convertida` | Unidade nova (ex.: `"75 minutos"`, `"1h15"`) | Ajustar a expressão regular da duração |
| `duracao_min ≠ encerramento − abertura` | As fontes de duração divergem | Investigar a origem antes de escolher qual vale |
| `causa`/`tipo` fora do domínio | Categoria nova | Confirmar com o negócio e incluir em `CAUSAS_VALIDAS`/`TIPOS_VALIDOS` |
| `id_ocorrencia repetido` | Mesma ocorrência com dados diferentes | Decidir com o negócio qual versão vale |

### 6.5. No Workflow (Job)
```text
landing_to_bronze ──► bronze_to_silver_ocorrencias_rede ──► (Gold de DEC/FEC)
```
No Databricks: **Jobs & Pipelines → Create → Job**. Adicione uma tarefa *Notebook* por notebook e marque **Depends on**. O notebook não tem parâmetros.

---

## 7. Como usar na Gold (DEC e FEC)

Pela definição do case, cada linha é uma UC interrompida. Para um alimentador num período:
* **DEC** (horas por UC) = `SUM(duracao_efetiva_min) / 60` ÷ número de UCs do alimentador;
* **FEC** (interrupções por UC) = `COUNT_IF(NOT flag_sobreposicao)` ÷ número de UCs do alimentador.

O número de UCs por alimentador vem do cadastro (Silver de `unidades_consumidoras`).

Como a sobreposição é calculada dentro do mês, os numeradores de qualquer período saem da soma dos meses dele, com ou sem os meses de evento atípico.

```sql
-- Numeradores de DEC/FEC por alimentador e mês, com a marcação de evento atípico
SELECT alimentador, ano_mes,
       SUM(duracao_efetiva_min) / 60.0                       AS horas_sem_energia,
       COUNT_IF(NOT flag_sobreposicao)                       AS interrupcoes,
       BOOL_OR(flag_evento_atipico)                          AS evento_atipico
FROM `v-energy`.silver.tb_ocorrencias_rede
GROUP BY alimentador, ano_mes;
```

Prévia com a base atual (soma dos 48 meses):

| Alimentador | Horas sem energia | Interrupções | Horas sem o evento atípico | Interrupções sem o evento atípico |
| :--- | :---: | :---: | :---: | :---: |
| `ALM-REC-008` | 35.645,9 | 8.063 | 2.111,5 | 1.324 |
| `ALM-SAO-004` | 18.361,7 | 4.602 | 2.088,7 | 1.313 |
| `ALM-JAB-004` | 14.826,2 | 3.868 | 2.267,4 | 1.315 |
| `ALM-REC-014` | 2.644,6 | 1.456 | 2.644,6 | 1.456 |
| `ALM-CAM-003` | 2.628,9 | 1.473 | 2.628,9 | 1.473 |

Sem o evento atípico, o ranking de "piores alimentadores" muda completamente. Por isso a escolha entre com e sem evento precisa ser explícita na Gold e no portal.

---

## 8. Testes realizados

O notebook foi executado sem modificações num Spark 4.0.1 + Delta 4.0.0 local (ANSI ligado), em cadeia com o notebook da Bronze. O resultado foi comparado com um cálculo independente feito em Python puro sobre o CSV:
* contagens, distribuições de `tipo` e `causa`, as somas de duração (21.392.087 e 21.348.526), as 331 sobreposições (268 em 2025-07), as 179.669 interrupções distintas, os meses de evento atípico (os 3 de 2025-07, com 12.836 ocorrências) e os exemplos, na versão com a sobreposição sobre toda a série (hoje são 330 sobreposições, 21.348.560 min efetivos e 179.670 interrupções; ver abaixo) (`"217 min"` → 217; `OC00122507` → 80 min efetivos) bateram 100%;
* os horários não mudam quando o fuso da sessão muda;
* as variações `" n/a "` e `"55 MIN"` são aceitas;
* a reexecução produz o mesmo resultado e só uma versão Delta nova;
* **5 defeitos injetados na Bronze** foram barrados pela regra certa, com a Silver intacta:
  * duração `"75 minutos"`;
  * encerramento antes da abertura;
  * causa nova `RAIO`;
  * mesmo id com conteúdo diferente;
  * data impossível `2022-13-01`.
* **Alimentador novo ou desativado:** simulando o `ALM-CAM-003` só a partir de 2026-01 e o `ALM-REC-014` só até 2022-12, só os 3 meses de 2025-07 continuam marcados. Sem o limite de período, 6 meses normais de cada um seriam marcados.
* **Cenários da review do muliroZ no PR #23**, com a Bronze alterada e a sessão em UTC, como no Serverless (versão anterior → versão atual):
  * ocorrência de evento atípico de 31/07 a 02/08 cobrindo uma normal de 01/08 na mesma UC do `ALM-REC-008`: na anterior, a normal ficava com 0 min, e o agosto "sem evento" do alimentador tinha 2.898 min; agora ela conta 240 min, e o agosto tem 3.138 min;
  * Bronze recarregada com 170.000 linhas entre a validação e a escrita: a anterior gravou as 170.000, que não tinham sido validadas; agora grava as 180.000 validadas;
  * alimentadores com série curta, meses [30, 600] e [600]: a anterior não marcava nenhum mês; agora o mês de 600 é marcado nos dois. Alimentador esparso, com 24 meses e um mês de 7: a anterior marcava o mês de 7; agora não;
  * nenhuma ocorrência na rede em 2023-03: na anterior, o mês ficava fora da série (5.734 células); agora entra com zero (5.856 = 122 × 48);
  * abertura 2 horas no futuro na hora de Recife: a anterior gravou; agora é barrada;
  * 1.000 ids em minúsculas e durações `"NNNMIN"` na Bronze: na anterior, a evidência 1 perdia as 1.000 ocorrências e a 2 contava `"NNNMIN"` como só dígitos; agora as duas cobrem as 180.000.
* **Com a Bronze original**, só uma linha muda em relação à versão anterior: a `OC00169819` (`UC139797`, 01/03/2026 das 01:46 às 02:20), que era coberta por uma interrupção aberta em fevereiro e agora conta seus 34 min. As outras 179.999 linhas são idênticas, e os 3 meses de evento atípico e as 12.836 ocorrências marcadas não mudam. Os 5 defeitos e o cenário de alimentador novo ou desativado continuam com o mesmo resultado.
* `ruff check` e `ruff format --check`, com a configuração do `pyproject.toml`, passam no notebook. `spark` e `display` são globais do Databricks, liberados com `# ruff: noqa: F821` na primeira célula.

**Databricks (Serverless):** o notebook também foi executado no Unity Catalog (na época em `venergy.silver`, antes da troca para os nomes da Bronze unificada), e a tabela de validação, os totais e as evidências deram os mesmos números do teste local.

---

## 9. Pendências e pontos que dependem de outras tabelas

* **Cadastro (`unidades_consumidoras`):** a Bronze do cadastro já está carregada pela Bronze unificada (PR #14), e conferi nela que todo `id_uc` das ocorrências existe no cadastro e que o `alimentador` da ocorrência é o mesmo da UC (100% nos dois casos). Dependem da Silver do cadastro (PR #24), que trata as UCs repetidas e as datas implausíveis:
  * marcar as **595 ocorrências abertas antes da `data_ligacao`** da UC (auditoria, seção 4.3);
  * usar o número de UCs por alimentador como denominador do DEC/FEC.
* **Meses 2025-11 e 2026-02:** o excesso difuso (≈ 3.885 ocorrências) continua registrado na auditoria como ponto a investigar. A regra de evento atípico corretamente **não** o marca, porque nenhum alimentador passa de 2,3× a base mensal.
