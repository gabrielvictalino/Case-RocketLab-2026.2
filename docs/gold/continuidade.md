# Gold de continuidade (DEC/FEC)

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-continuidade.ipynb` |
| **Entradas** | `` `v-energy`.silver.tb_ocorrencias_rede `` (PR #23) e `` `v-energy`.silver.tb_unidades_consumidoras `` (PR #24) |
| **Saídas** | `` `v-energy`.gold.dim_alimentador ``, `` `v-energy`.gold.ocorrencias_uc `` e `` `v-energy`.gold.continuidade_alimentador_mensal `` |
| **Contrato** | `contracts/tabelas/dim_alimentador.yaml`, `ocorrencias_uc.yaml` e `continuidade_alimentador_mensal.yaml` |
| **Usada por** | Continuidade no backend (#57), tela Operação (#58) e visão 360 da UC |

## 1. A pergunta

A Gerente de Operação (Beatriz Farias) pede, na seção 4.2 do case: _"A ANEEL cobra DEC e FEC da gente, e multa quando passamos do limite. Quero acompanhar esses indicadores por alimentador ao longo do tempo e identificar os piores, para direcionar a manutenção preventiva."_ A user story de dados correspondente é calcular DEC e FEC por alimentador conforme a definição da ANEEL. O system design (seção 13, pendência 4) deixou para o time de dados três pontos: a sobreposição de interrupções, o denominador por alimentador e a marcação de evento atípico.

## 2. Definições

Pelo glossário do case (seção 3.2), cada ocorrência é uma UC interrompida, e os valores servem para comparar alimentadores e períodos entre si, não com os limites regulatórios reais. Para um alimentador numa competência:

* **CHI** (UC × hora) = `SUM(duracao_efetiva_min) / 60` das ocorrências do alimentador na competência;
* **interrupções** = ocorrências com `flag_sobreposicao = false`;
* **DEC** (horas por UC) = CHI ÷ número de UCs do alimentador;
* **FEC** (interrupções por UC) = interrupções ÷ número de UCs do alimentador.

**Período maior** (um ano, um ciclo, o período inteiro): some o CHI e as interrupções das competências e divida pelo número de UCs. Para um conjunto de alimentadores, divida pela soma das UCs deles. Nunca tire a média dos DECs mensais: um alimentador pequeno pesaria o mesmo que um grande. Por isso a tabela guarda os numeradores (`chi_horas`, `interrupcoes`) e o denominador (`numero_ucs`) ao lado do DEC e do FEC.

**Com ou sem evento atípico:** a tabela traz todas as competências, e `flag_evento_atipico` marca as do evento. Excluir o evento é filtrar `NOT flag_evento_atipico` antes de somar. O glossário define CHI como o critério padrão para priorizar manutenção, e o padrão do ranking no backend (#57) é o CHI.

## 3. Regras e decisões

### 3.1. Numeradores vêm prontos da Silver

A Silver de ocorrências calcula a sobreposição dentro de cada UC e competência (`docs/silver/silver_ocorrencias_rede.md`, seções 2.4 e 7):

* `duracao_efetiva_min` tira os minutos em que a UC já estava sem energia por outra ocorrência. Somar `duracao_min` contaria 43.527 min em dobro.
* `flag_sobreposicao = true` marca a ocorrência que começou com a UC já sem energia. Ela não é uma interrupção nova: das 180.000 ocorrências, 179.670 contam no FEC.

Como a sobreposição é calculada dentro da competência, os numeradores de qualquer período saem da soma das competências dele, com ou sem as de evento atípico.

### 3.2. Denominador: UCs do alimentador no cadastro

`numero_ucs` é o número de UCs do alimentador na Silver de cadastro, o mesmo em todas as competências. Hoje são 45.000 UCs em 122 alimentadores, de 20 a 2.285 UCs cada.

A alternativa seria contar, em cada competência, só as UCs com `data_ligacao` até o fim do mês. Ela foi descartada:

* só 362 UCs (0,8%) foram ligadas dentro do período das ocorrências (jul/2022 a jun/2026), então o denominador mudaria menos de 1%;
* 595 ocorrências foram abertas antes da `data_ligacao` da própria UC (auditoria, seção 4.3), e 289 são de UCs sem `data_ligacao` (as datas sentinela que a Silver de cadastro anulou). Com o denominador por data de ligação, essas UCs entrariam no numerador e ficariam fora do denominador.

As 595 ocorrências entram no DEC e no FEC: a interrupção registrada é evidência de que a UC era atendida, e a data de ligação é o dado menos confiável dos dois. O notebook imprime as duas contagens a cada execução.

### 3.3. Grade completa: alimentador × competência

A tabela mensal tem uma linha para cada alimentador do cadastro em cada competência entre a primeira e a última ocorrência (calendário gerado com `sequence`). Um mês sem nenhuma ocorrência entra com CHI, interrupções, DEC e FEC iguais a zero, e `causa = 'SEM OCORRENCIA'`. Sem a linha, uma consulta que conta meses ou tira a média por mês veria só os meses com interrupção. Hoje a grade é 122 × 48 = 5.856 linhas, e todo alimentador tem ocorrência em todo mês.

### 3.4. Causa principal

O contrato tem uma `causa` por linha na tabela mensal, que tem chave alimentador × competência. Ela é a **causa principal** do mês: a causa com mais minutos efetivos no alimentador. No empate, vence a causa com mais interrupções e, depois, a primeira em ordem alfabética.

Hoje há 14 meses com empate nos minutos. As interrupções desempatam 11, e a ordem alfabética os outros 3 (`ALM-JAB-009` em 2023-04, `ALM-JAB-020` em 2025-06 e `ALM-PAU-002` em 2023-01).

A causa principal é um atributo do mês, não um recorte do DEC. Para o tempo e as interrupções de cada causa, use `ocorrencias_uc`. Nela, os minutos em comum ficam com a interrupção que já estava em curso, e a soma por causa fecha com o total (seção 2.4 da Silver).

### 3.5. Evento atípico

`flag_evento_atipico` vem da Silver: uma competência é de evento atípico quando o alimentador passa de 5× a sua base mensal de ocorrências. A Gold confere que a marcação é a mesma em todas as ocorrências de um alimentador e competência e a leva para a linha mensal. Hoje são 3 linhas: `ALM-REC-008`, `ALM-SAO-004` e `ALM-JAB-004` em 2025-07. A marcação não remove nada.

### 3.6. Arredondamento

`chi_horas`, `dec` e `fec` são `numeric(18,2)`, como no contrato. Cada valor é calculado dos minutos exatos e arredondado uma vez, com meio para cima. A mediana do DEC mensal de um alimentador é 0,16 h, então o arredondamento em centésimos pesa no valor de um mês. Por isso a reagregação usa `chi_horas` e `interrupcoes`, e não a soma de `dec` e `fec`.

### 3.7. `ocorrencias_uc` e `dim_alimentador`

* `ocorrencias_uc` é a Silver de ocorrências com as colunas do contrato. As durações passam de inteiro para `numeric(18,2)`, e as datas continuam `TIMESTAMP_NTZ` (hora local, sem fuso).
* `dim_alimentador` tem o município das UCs do alimentador e o número delas. O notebook bloqueia a carga se um alimentador tiver UCs em mais de um município.

## 4. Dicionário de dados

### `` `v-energy`.gold.continuidade_alimentador_mensal `` (alimentador × competência)

| Coluna | Tipo | Nulo? | Descrição |
| :--- | :--- | :---: | :--- |
| `alimentador` | STRING | não | Alimentador (`^ALM-[A-Z]{3}-\d{3}$`). Chave com `competencia` |
| `competencia` | DATE | não | Primeiro dia do mês |
| `numero_ucs` | INT | não | UCs do alimentador no cadastro (seção 3.2). Mínimo 1 |
| `chi_horas` | DECIMAL(18,2) | não | Soma das horas sem energia das UCs interrompidas, sem os minutos em comum |
| `interrupcoes` | INT | não | Ocorrências que não começaram com a UC já sem energia |
| `dec` | DECIMAL(18,2) | não | `chi_horas ÷ numero_ucs`, horas por UC |
| `fec` | DECIMAL(18,2) | não | `interrupcoes ÷ numero_ucs`, interrupções por UC |
| `causa` | STRING | não | Causa principal do mês (seção 3.4), ou `SEM OCORRENCIA` |
| `flag_evento_atipico` | BOOLEAN | não | Competência de evento atípico do alimentador (seção 3.5) |

### `` `v-energy`.gold.ocorrencias_uc `` (ocorrência por UC)

| Coluna | Tipo | Nulo? | Descrição |
| :--- | :--- | :---: | :--- |
| `id_ocorrencia` | STRING | não | Identificador da ocorrência (chave) |
| `id_uc` | STRING | não | UC interrompida; existe na Silver de cadastro (`dim_uc`) |
| `alimentador` | STRING | não | Alimentador da UC; existe em `dim_alimentador` |
| `data_abertura` | TIMESTAMP_NTZ | não | Início da interrupção, hora local |
| `data_encerramento` | TIMESTAMP_NTZ | não | Fim da interrupção, hora local |
| `duracao_min` | DECIMAL(18,2) | não | Duração registrada |
| `duracao_efetiva_min` | DECIMAL(18,2) | não | Minutos não cobertos por outra ocorrência da mesma UC na competência. Some esta coluna para o tempo sem energia |
| `causa` | STRING | não | Causa da ocorrência (6 causas ou `NAO INFORMADA`) |
| `flag_sobreposicao` | BOOLEAN | não | A UC já estava sem energia quando a ocorrência começou. Conte as linhas com `false` para as interrupções |

### `` `v-energy`.gold.dim_alimentador `` (alimentador)

| Coluna | Tipo | Nulo? | Descrição |
| :--- | :--- | :---: | :--- |
| `alimentador` | STRING | não | Alimentador (chave) |
| `municipio` | STRING | não | Município das UCs do alimentador, com a grafia do cadastro |
| `numero_ucs` | INT | não | UCs do alimentador no cadastro |

## 5. Validações

Todas bloqueiam a carga. A Gold anterior continua intacta quando uma falha acontece antes da escrita.

**Nas Silvers, antes de montar a Gold:** colunas esperadas; `id_ocorrencia` sem nulo nem repetição; `id_uc` e `alimentador` no padrão; causa preenchida; `competencia` igual ao mês da abertura; `duracao_efetiva_min` em [0, `duracao_min`]; flags preenchidas; evento atípico constante em cada alimentador × competência; no cadastro, `id_uc` único, alimentador no padrão, município preenchido e um município por alimentador; toda UC das ocorrências no cadastro, no mesmo alimentador.

**Nas três tabelas, em memória e de novo depois de gravar:**

* contrato: tipos, nulos, padrões, mínimos e chaves;
* grade: linhas = alimentadores × competências;
* reconciliação: soma das interrupções igual às ocorrências sem sobreposição; soma do CHI igual aos minutos efetivos ÷ 60, dentro do arredondamento; `ocorrencias_uc` com as mesmas linhas e as mesmas somas de duração da Silver; soma das UCs da `dim_alimentador` igual ao cadastro;
* coerência: DEC e FEC a até 0,01 do CHI e das interrupções divididos pelas UCs; mês sem interrupção com CHI zero e `SEM OCORRENCIA`; competências de evento atípico iguais às da Silver; `numero_ucs` igual ao da `dim_alimentador`; `id_uc` presente no cadastro e `alimentador` presente na `dim_alimentador`.

**Publicação:** antes da primeira escrita, o notebook guarda a versão de cada tabela de destino. Se a escrita, a conferência do conteúdo gravado ou a validação sobre as tabelas gravadas falhar, ele volta cada tabela afetada com `RESTORE TABLE ... TO VERSION AS OF`, ou a remove se era a primeira carga.

## 6. Números da base atual

180.000 ocorrências, 179.670 interrupções e 21.348.560 minutos efetivos (355.809,14 h de CHI), em 122 alimentadores e 48 competências (5.856 linhas mensais), com 45.000 UCs.

**DEC e FEC de todos os alimentadores por ciclo de julho a junho:**

| Ciclo | DEC | FEC | DEC sem evento atípico | FEC sem evento atípico |
| :--- | :---: | :---: | :---: | :---: |
| 2022-07 a 2023-06 | 1,47 | 0,89 | 1,47 | 0,89 |
| 2023-07 a 2024-06 | 1,50 | 0,90 | 1,50 | 0,90 |
| 2024-07 a 2025-06 | 1,50 | 0,90 | 1,50 | 0,90 |
| 2025-07 a 2026-06 | 3,43 | 1,30 | 2,05 | 1,02 |

O último ciclo tem o evento de 2025-07. Sem as três competências marcadas, o DEC ainda sobe de 1,50 para 2,05:

| Competências | Alimentadores | Interrupções por mês | Minutos efetivos por interrupção | CHI do mês ÷ 45.000 UCs |
| :--- | :---: | :---: | :---: | :---: |
| Meses normais | 122 | 3.366 | 99,6 | cerca de 0,12 |
| 2025-11 e 2026-02 | 122 | 5.306 | 99,5 | 0,20 e 0,19 |
| 2025-07, sem os 3 marcados | 119 | 4.995 | 292,5 | 0,54 |

A maior parte do aumento vem do próprio 2025-07 nos outros 119 alimentadores: eles tiveram 1,5 vez mais interrupções que num mês normal, abaixo do limite de 5× da Silver, e cada uma durou quase o triplo. O excesso difuso de 2025-11 e 2026-02, que a auditoria deixou para investigar, vem do número de interrupções, com a duração normal.

**Piores alimentadores no período inteiro, por CHI:**

| Com o evento atípico | CHI (h) | DEC | Sem o evento atípico | CHI (h) | DEC |
| :--- | :---: | :---: | :--- | :---: | :---: |
| `ALM-REC-008` | 35.645,89 | 15,60 | `ALM-REC-014` | 2.644,53 | 7,80 |
| `ALM-SAO-004` | 18.361,68 | 16,83 | `ALM-CAM-003` | 2.628,89 | 12,82 |
| `ALM-JAB-004` | 14.826,18 | 17,18 | `ALM-JAB-013` | 2.626,33 | 4,81 |
| `ALM-REC-014` | 2.644,53 | 7,80 | `ALM-JAB-017` | 2.587,34 | 4,01 |
| `ALM-CAM-003` | 2.628,89 | 12,82 | `ALM-OLI-009` | 2.578,62 | 9,02 |

Com o evento, os três alimentadores atingidos lideram por larga margem. Sem ele, o CHI dos primeiros fica entre 2.500 e 2.650 h, e o DEC separa alimentadores pequenos com muitas horas por UC (`ALM-CAM-004`: 147 UCs, DEC 17,42) de alimentadores grandes com muitas horas no total. A escolha entre CHI e DEC, e entre com e sem o evento, precisa ficar explícita no portal.

**CHI por causa (`ocorrencias_uc`):**

| Causa | CHI (h) | Interrupções |
| :--- | :---: | :---: |
| `CLIMATICA` | 128.249,15 | 43.421 |
| `SOBRECARGA` | 44.124,52 | 26.318 |
| `VEGETACAO` | 43.792,08 | 26.143 |
| `NAO IDENTIFICADA` | 43.401,77 | 26.319 |
| `TERCEIROS` | 42.975,55 | 26.137 |
| `FALHA DE EQUIPAMENTO` | 42.792,42 | 25.938 |
| `NAO INFORMADA` | 10.473,85 | 5.394 |

## 7. Decisões e alternativas

| Decisão | Alternativa descartada | Motivo |
| :--- | :--- | :--- |
| CHI pelos minutos efetivos e FEC pelas ocorrências sem sobreposição | `SUM(duracao_min)` e `COUNT(*)` | A soma direta conta 43.527 min e 330 interrupções em dobro |
| Denominador fixo: UCs do alimentador no cadastro | UCs com `data_ligacao` até o fim de cada mês | Muda menos de 1%, e 595 ocorrências são anteriores à data de ligação da UC (seção 3.2) |
| Grade completa, mês sem ocorrência com zero | Só os meses com ocorrência | Contagem e média de meses corretas no portal e no agente |
| Uma causa principal por linha, a de mais minutos | Grão alimentador × competência × causa | Mantém a chave do contrato; o recorte por causa está em `ocorrencias_uc` |
| Numeradores e denominador ao lado do DEC e do FEC | Só o DEC e o FEC | Reagregação de qualquer período sem média de DECs |
| Evento atípico marcado, nunca removido | Tirar o evento na Gold | O portal escolhe com ou sem; o ranking muda completamente |

## 8. Como executar no Databricks

1. **Pré-requisito:** as duas Silvers publicadas.

   ```sql
   SELECT COUNT(*) FROM `v-energy`.silver.tb_ocorrencias_rede;      -- esperado: 180000
   SELECT COUNT(*) FROM `v-energy`.silver.tb_unidades_consumidoras; -- esperado: 45000
   ```

2. Importe o notebook, conecte ao **Serverless** e use **Run all**. O padrão `modo=validar` não grava nada; para gravar, o Job passa `modo=publicar` (ou troque o widget antes de executar).
3. **O que conferir:**
   * todas as linhas `[OK   ]` em `(fontes)` e `(antes de gravar)`;
   * `Reconciliação: 180,000 ocorrências | 179,670 interrupções | 21,348,560 minutos efetivos = 355,809.14 h de CHI | 122 alimentadores × 48 competências = 5,856 linhas`;
   * `Informativo: 595 ocorrências abertas antes da data_ligacao da UC e 289 de UCs sem data_ligacao`;
   * com `modo=validar`, a linha final `Validação concluída. Nenhum schema ou tabela foi gravado.`;
   * com `modo=publicar`, as linhas `[OK   ]` em `(tabela gravada)` e as três linhas `Publicada: ...`.

Se uma validação falhar, a mensagem lista cada regra violada com a quantidade de linhas. Uma falha nas `(fontes)` aponta para a Silver de origem; uma falha em `(tabela gravada)` já restaurou a Gold anterior.

## 9. Pendências

* **Contrato provisório:** os três YAMLs continuam como `provisorio-nao-aprovado`. O backend (#57) aceita a causa principal por linha (seção 3.4) e o valor `SEM OCORRENCIA` como atributos mensais; o ranking conta ocorrências por causa no detalhe `ocorrencias_uc`. O aceite desse consumo não homologa a exportação real nem aprova o contrato inteiro.
* **Evento atípico pela duração:** a Silver marca a competência pelo número de ocorrências do alimentador. Em 2025-07, os 119 alimentadores não marcados ficaram abaixo do limite em número, mas com interrupções quase três vezes mais longas (seção 6). Se o portal precisar excluir o evento inteiro, a regra da Silver (PR #23) precisa considerar também o CHI do mês, decisão a combinar com o dono da Silver.
* **Exportação para o banco local:** fica no passo único de exportação do Job (system design, seção 13, pendência 9).
* **Recorte "sem esta causa":** se o portal precisar, dá para acrescentar a união dos intervalos por UC, competência e causa (Silver, seção 2.4).
