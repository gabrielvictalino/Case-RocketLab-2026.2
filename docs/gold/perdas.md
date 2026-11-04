# Gold de perdas

| | |
| :--- | :--- |
| **Notebook** | `data-engineering/silver_to_gold/silver-to-gold-perdas.ipynb` |
| **Entradas** | `` `v-energy`.silver.tb_leituras ``, `tb_unidades_consumidoras`, `tb_medidores`, `tb_inspecoes` e `tb_faturas` (pela revisão indicada em `tb_faturas_publicacao`), e `` `v-energy`.gold.gd_uc `` |
| **Saídas** | `` `v-energy`.gold.inspecoes_historicas `` e `` `v-energy`.gold.fila_inspecao `` |
| **Contrato** | `contracts/tabelas/inspecoes_historicas.yaml` e `fila_inspecao.yaml` |
| **Usada por** | Tela de Perdas e geração de ordens (`backend/app/modules/perdas`), views `portal_read.inspecoes`, `ai_read.inspecoes` e `ai_read.fila_inspecao` (`importador/views.sql`) e gate R4 do importador |

## 1. A pergunta

O Gerente de Perdas (Rafael Coutinho) pede, na seção 4.2 do case: _"Pouco mais da metade [das inspeções] encontra alguma irregularidade. Quero uma fila das unidades suspeitas, da mais promissora para a menos promissora, com o motivo da suspeita e quanta energia dá para recuperar."_ Hoje, 871 das 1.389 inspeções confirmaram irregularidade (62,7%).

A Gold responde com duas tabelas: o histórico das inspeções feitas e a fila das UCs que ainda valem uma inspeção, cada uma com um score, os motivos e a energia estimada.

## 2. Regras e decisões

### 2.1. `inspecoes_historicas`: uma inspeção por linha

Cópia tipada da Silver de inspeções (`docs/silver/silver_inspecoes.md`), com as colunas, os padrões e o domínio do contrato. A Gold confere duas coerências do contrato: inspeção confirmada tem tipo de irregularidade, e inspeção sem irregularidade não tem tipo nem energia recuperada.

### 2.2. Quem entra na fila

Uma UC entra na fila quando cumpre as quatro condições:

1. **Consumo caiu pelo menos 40%** em relação ao primeiro ano da própria UC. A queda compara a média dos 3 meses antes do mês de referência da fila (o seguinte à última leitura, hoje 07/2026) com a média do P0 (jul/2022 a jun/2023). As duas médias usam só leituras utilizáveis (`docs/silver/silver_leituras.md`, seção 5), com pelo menos 2 meses na janela recente e 6 no P0.
2. **Não tem GD** (R4). A queda de quem instalou placa solar é legítima: 3.394 UCs com GD caíram 40% ou mais e ficam de fora.
3. **A última inspeção não confirmou fraude** (seção 2.7).
4. Tem tarifa média para converter a energia em R$ (seção 2.6). Hoje, todas têm.

**Por que 40%, e não 10% ou 30%.** A queda foi medida nas 1.389 inspeções só com dados anteriores a cada uma (contra o P0, com os 3 meses antes da inspeção):

| Queda antes da inspeção | Inspeções | Confirmadas | Acerto |
| :--- | ---: | ---: | ---: |
| menos de 30% | 274 | 22 | 8,0% |
| de 30% a 40% | 123 | 9 | 7,3% |
| de 40% a 50% | 124 | 69 | 55,6% |
| 50% ou mais | 826 | 764 | 92,5% |
| UC com GD | 31 | 1 | 3,2% |
| sem leituras suficientes | 11 | 6 | 54,5% |

Abaixo de 40%, o acerto é o mesmo de quem quase não caiu. A partir de 40%, ele sobe para 56%; a partir de 50%, para 93%.

### 2.3. Score de 0 a 100: soma de pontos

| Sinal | Pontos |
| :--- | ---: |
| Queda de 40% a 50% / de 50% ou mais | 35 / 60 |
| Medidor eletromecânico na data de referência | +15 |
| 30% ou mais das leituras estimadas nos 12 meses antes da referência | +15 |
| Desempate: 10 × queda (queda de 62% = 6,2 pontos) | até +10 |

A queda pesa mais, com um degrau em 50%, porque é o sinal que mais separa. Medidor e leituras estimadas separam dentro da faixa de 40% a 50%: nas 124 inspeções dessa faixa, o medidor eletromecânico acertou 75,6%, contra 10,5% dos demais; com 30% ou mais de leituras estimadas, 78,8%, contra 13,6%. A partir de 50% de queda, o acerto fica em torno de 93% com ou sem esses sinais, e abaixo de 40% eles não separam. Os pontos saem dessa separação, e não de opinião.

O score ordena as inspeções passadas: quanto mais alto, maior o acerto (UCs sem GD com queda de 40% ou mais).

| Score | Inspeções | Confirmadas | Acerto |
| :--- | ---: | ---: | ---: |
| 90 ou mais | 657 | 607 | 92,4% |
| 75 a 90 | 166 | 156 | 94,0% |
| 60 a 75 | 82 | 64 | 78,0% |
| menos de 60 | 45 | 6 | 13,3% |

O notebook para se o score deixar de ordenar (acerto com score ≥ 60 não maior que com score < 60). Hoje: 91,4% contra 13,3%. A tabela mede o acerto nas mesmas inspeções usadas para escolher os pontos, então é uma checagem de coerência, não uma previsão.

**Na reinspeção, só a queda nova pontua.** Para a UC cuja última inspeção não achou irregularidade, a queda que dá pontos (e o desempate) compara o consumo recente com o dos 3 meses antes da inspeção, e não com o P0. A queda contra o P0 continua decidindo quem entra na fila (seção 2.2). O motivo é que o inspetor já foi até a UC com essa queda e não achou nada:

* as 68 reinspeções da fila já tinham queda de 40% ou mais contra o P0 nos 3 meses antes da inspeção (61 delas, de 50% ou mais);
* a mediana dessa queda era de 63,0% na inspeção e é de 56,5% hoje, então o consumo não caiu mais depois;
* os 92,5% de acerto da seção 2.2 vêm de primeiras inspeções: nenhuma UC da base foi inspecionada duas vezes, então não há como medir o acerto de uma reinspeção.

Sem queda nova de 40%, uma reinspeção soma no máximo os pontos do medidor, das leituras estimadas e o desempate de uma queda abaixo de 40%: até 34 pontos. Uma UC nunca inspecionada começa em 39 (queda de 40%, sem outros sinais). As reinspeções ficam, então, abaixo de todas as nunca inspecionadas, e o notebook para se alguma reinspeção sem queda nova chegar a 39. Hoje, nenhuma reinspeção tem queda nova de 40% ou mais, e o maior score entre elas é 31,64.

### 2.4. Bairro e classe não pontuam nem viram motivo

Os 4 bairros mais inspecionados têm 8% das UCs, mas receberam 67% das inspeções e concentram 96% das irregularidades confirmadas:

| Onde | UCs | Inspeções | Confirmadas |
| :--- | ---: | ---: | ---: |
| Recife / Iputinga | 1.234 | 310 | 282 |
| Jaboatão dos Guararapes / Jardim Jordão | 1.111 | 299 | 268 |
| Jaboatão dos Guararapes / Prazeres | 668 | 168 | 151 |
| Recife / Macaxeira | 561 | 151 | 134 |
| Demais 293 bairros | 41.426 | 461 | 36 |

Só se acha fraude onde se procura. Se o bairro desse pontos, a fila mandaria as equipes de volta aos mesmos 4 bairros e repetiria a escolha de quem fez as inspeções. A queda de consumo vale igual em qualquer bairro. Município, bairro e classe continuam visíveis na tela da fila, que filtra por eles, então também não entram nos motivos. Pelo mesmo viés, o "Motivo da suspeita" do `GLOSSARY.md` não lista a localização entre os sinais.

### 2.5. Motivos: uma lista de textos

O importador aceita o `jsonb` de `motivos` só como lista de textos não vazios, e o backend tipa `list[str]`. Cada texto traz o sinal e o valor. A Gold guarda a lista como `array<string>`, e a exportação consolidada (#96) a escreve em JSON. A UC mais bem colocada hoje:

```
Consumo 51% abaixo do primeiro ano da própria UC: 92 kWh/mês de 04/2026 a 06/2026, contra 190 kWh/mês de 07/2022 a 06/2023
50% das leituras estimadas de 07/2025 a 06/2026
Medidor eletromecânico
```

Numa reinspeção, o último motivo diz quando foi a inspeção e como o consumo mudou desde então (seção 2.3):

```
Consumo 61% abaixo do primeiro ano da própria UC: 84 kWh/mês de 04/2026 a 06/2026, contra 214 kWh/mês de 07/2022 a 06/2023
42% das leituras estimadas de 07/2025 a 06/2026
Medidor eletromecânico
Inspecionada em 17/10/2025 sem irregularidade constatada; consumo recente 63% maior que nos 3 meses antes da inspeção (52 kWh/mês)
```

O primeiro motivo existe em toda linha; os outros aparecem quando o sinal está presente.

### 2.6. Energia a recuperar, em kWh e em R$

* **`energia_recuperar_kwh`** = queda mensal (kWh do P0 − kWh recentes) × **fator de energia**. O fator é a mediana de `kwh_recuperado ÷ queda mensal` nas inspeções confirmadas de UCs sem GD com queda de 40% ou mais, calculado a cada execução: hoje, 5,6132 em 833 confirmadas, com correlação de 0,918 entre a queda e a energia recuperada. Ou seja, uma irregularidade que derruba 100 kWh por mês recupera cerca de 561 kWh. O notebook para se o fator sair de 1 a 12.
* **`energia_recuperar_reais`** = kWh × tarifa média da UC: valor da energia ÷ consumo utilizável nos meses com fatura e leitura dos 12 meses antes da referência. A tarifa usa o `valor_energia` das faturas, sem os `tributos`, que nesta base são 1/3 desse valor (o `valor_total` é a soma dos dois). Por isso, o R$ da fila não se compara com o `valor_total` das faturas. Sem esses meses, vale a mediana do subgrupo tarifário. Hoje as 141 UCs da fila têm tarifa própria; as medianas são R$ 0,6056/kWh no B1 (120 UCs), R$ 0,6715 no B3 (20) e R$ 0,6738 no B2 (1). As faturas são lidas pelo marcador `tb_faturas_publicacao`, como pede `docs/auditoria_dados/operacao_faturas.md`.

### 2.7. UCs com fraude já confirmada saem da fila

Na base, o consumo das UCs com irregularidade confirmada não volta ao nível anterior depois da inspeção:

| Período em relação à inspeção | Confirmadas (kWh/mês) | Sem irregularidade (kWh/mês) |
| :--- | ---: | ---: |
| 13 a 24 meses antes | 491 | 381 |
| 7 a 12 meses antes | 549 | 411 |
| 4 a 6 meses antes | 367 | 340 |
| 1 a 3 meses antes | 190 | 297 |
| até 5 meses depois | 270 | 392 |
| 6 meses ou mais depois | 232 | 293 |

Com essas UCs, a fila teria 828 casos já resolvidos entre 969 candidatas. Elas ficam de fora: a irregularidade já foi tratada, e a energia dela já está em `inspecoes_historicas`. Vale qualquer inspeção confirmada, e não só a última: uma UC confirmada que depois passe por uma inspeção sem irregularidade continua fora, para a energia não ser contada duas vezes. Hoje nenhuma UC tem mais de uma inspeção. As UCs inspecionadas sem irregularidade que continuam com consumo baixo ficam na fila como reinspeção, abaixo das nunca inspecionadas (seção 2.3), com o motivo que diz quando foi a inspeção e quanto o consumo mudou desde então.

### 2.8. O "92% de acerto" dos docs de overview

Os docs de `docs/overview_dados/` e `docs/diagnostico_receita.md` dizem que 92% das UCs inspecionadas com queda acima de 10% tinham fraude. O número se reproduz (seção 2, consulta 8 do notebook): comparando o P1 (jul/2025 a jun/2026) com o P0, 829 de 900 inspeções (92,1%) com queda acima de 10% confirmaram, contra 36 de 448 (8,0%) com queda de até 10%.

Só que o P1 inclui meses depois das inspeções (ago a dez/2025), quando o consumo das confirmadas segue baixo (seção 2.7). A fila só conhece o que aconteceu antes da inspeção. Com dados anteriores, o limite de 10% acerta bem menos, e o sinal está no tamanho da queda (seção 2.2).

## 3. Dicionário de dados

### `` `v-energy`.gold.inspecoes_historicas `` (inspeção)

| Coluna | Tipo | Nulo | Descrição |
| :--- | :--- | :---: | :--- |
| `id_inspecao` | `string` | Não | Identificador da inspeção (`IN` + 7 dígitos). Chave primária |
| `id_uc` | `string` | Não | UC inspecionada (`UC` + 6 dígitos) |
| `data` | `date` | Não | Data da inspeção |
| `inspetor` | `string` | Não | Código do inspetor (`INSP-001` a `INSP-040`) |
| `resultado` | `string` | Não | `IRREGULARIDADE CONFIRMADA` ou `SEM IRREGULARIDADE` |
| `tipo_irregularidade` | `string` | Sim | Tipo constatado; nulo quando não houve irregularidade |
| `kwh_recuperado` | `decimal(18,2)` | Não | Energia recuperada após a regularização; 0 sem irregularidade |

### `` `v-energy`.gold.fila_inspecao `` (UC candidata)

| Coluna | Tipo | Nulo | Descrição |
| :--- | :--- | :---: | :--- |
| `id_uc` | `string` | Não | UC candidata. Chave primária |
| `score` | `decimal(18,2)` | Não | Pontos de 0 a 100 da seção 2.3; quanto maior, mais promissora |
| `motivos` | `array<string>` | Não | Lista de sinais com valor (seção 2.5); vira `jsonb` na exportação |
| `energia_recuperar_kwh` | `decimal(18,2)` | Não | Energia estimada a recuperar se a irregularidade for confirmada |
| `energia_recuperar_reais` | `decimal(18,2)` | Não | A mesma energia em R$, pela tarifa média da UC |

## 4. Validações

Todas param o notebook antes de gravar e se repetem sobre as tabelas gravadas, com `RESTORE` em caso de falha:

* **Fontes:** padrões de `id_inspecao` e `id_uc`, data e resultado das inspeções; os 3 meses antes de cada inspeção depois do fim do P0 (jun/2023), para a calibração só usar dados anteriores a ela; colunas `municipio` e `bairro` do cadastro, usadas na seção 2 do notebook; mês e tipo das leituras; chaves únicas (inspeção, UC × mês, UC do cadastro); toda UC inspecionada no cadastro. As faturas só são lidas se o marcador tiver as duas linhas da mesma execução.
* **Calibração:** pelo menos 100 confirmadas com queda de 40% ou mais; fator de energia de 1 a 12; score ≥ 60 acertando mais que score < 60.
* **Candidatas:** toda UC da fila com tarifa média e com no máximo um medidor na data de referência; nenhuma reinspeção sem queda nova de 40% com score de 39 ou mais (o piso das nunca inspecionadas); nenhuma reinspeção com inspeção dentro dos 3 meses antes da referência, porque as duas janelas da queda nova (os 3 meses antes da inspeção e os 3 recentes) se sobreporiam.
* **`inspecoes_historicas`:** colunas, tipos e ordem do contrato; obrigatórias não nulas; padrões de `id_inspecao`, `id_uc` e `inspetor`; resultado no domínio; `kwh_recuperado` ≥ 0; confirmada com tipo; sem irregularidade sem tipo e com 0 kWh; linhas e soma de `kwh_recuperado` iguais às da Silver; chave única; UC no cadastro. Aviso (não para): tipo fora dos 5 da planilha.
* **`fila_inspecao`:** colunas, tipos e ordem do contrato; nada nulo; padrão de `id_uc`; chave única; score de 0 a 100; `motivos` com pelo menos um texto e nenhum vazio; energia ≥ 0; tarifa média implícita (R$ ÷ kWh) de R$ 0,10 a R$ 2,00; UC no cadastro; nenhuma UC de `gd_uc` (R4); nenhuma UC com fraude confirmada em alguma inspeção.

## 5. Números da base atual

| Item | Valor |
| :--- | :--- |
| Mês de referência da fila | 07/2026 (última leitura em 06/2026) |
| `inspecoes_historicas` | 1.389 inspeções, 1.473.112,00 kWh recuperados |
| `fila_inspecao` | 141 UCs: 73 nunca inspecionadas e 68 de reinspeção |
| Energia a recuperar (totais de controle) | 127.437,79 kWh e R$ 80.750,17 |
| Nunca inspecionadas | 44.751,96 kWh, R$ 28.034,39, score médio 50,3 |
| Reinspeção | 82.685,83 kWh, R$ 52.715,78, score médio 25,8 (máximo 31,64) |
| Fora da fila com queda ≥ 40% | 828 com fraude confirmada e 3.394 com GD |

As primeiras da fila são UCs nunca inspecionadas, com medidor eletromecânico e muitas leituras estimadas. As 68 reinspeções vêm depois, e a energia delas (65% do total em R$) depende de a inspeção anterior ter deixado passar uma irregularidade.

**Como apresentar o R$ da fila.** Sempre nas duas parcelas, e não como "R$ 80,7 mil a recuperar": R$ 28.034,39 das 73 nunca inspecionadas e R$ 52.715,78 das 68 reinspeções, que só se confirmam se a inspeção anterior deixou passar a irregularidade (seção 6).

**Expectativa de acerto.** Nas inspeções passadas, score abaixo de 60 acertou 13,3% (seção 2.3). As nunca inspecionadas da fila têm score médio de 50,3, então a maior parte delas está nessa faixa. A fila ordena bem, mas a chance de acerto cai rápido depois das primeiras posições.

## 6. Decisões e alternativas

| Decisão | Alternativa | Por que não |
| :--- | :--- | :--- |
| Queda de 40% ou mais | 10% (docs de overview) ou 30% | Com dados anteriores à inspeção, de 10% a 40% o acerto fica em 7% a 8% |
| P0 como período de comparação | Do mês −18 ao −7 antes da referência | Uma irregularidade iniciada há mais de 7 meses contaminaria a comparação |
| Soma de pontos com degrau | Modelo estatístico | A soma se explica em uma tabela e reproduz a ordem do acerto; com 1.389 inspeções, um modelo não acrescenta separação |
| Bairro e classe fora | Pontuar os bairros com mais fraude | Repetiria a concentração das inspeções (seção 2.4) |
| Fraude confirmada fora da fila | Manter como reinspeção | A fila teria 828 casos já tratados, e a energia seria contada duas vezes |
| Na reinspeção, só a queda nova pontua | Pontuar a queda contra o P0, como na primeira inspeção | A inspeção já usou essa queda e não achou nada; o acerto medido vale só para primeiras inspeções |
| Energia das reinspeções pela queda contra o P0, como nas nunca inspecionadas | Só a queda nova, como no score | A energia a recuperar é condicional à confirmação (`GLOSSARY.md`): se a reinspeção confirmar, a irregularidade já existia na inspeção anterior, e a perda é a queda inteira. Pela queda nova, as 68 reinspeções valeriam quase nada e ficariam na fila sem motivo. Por isso, o R$ da fila se apresenta em duas parcelas (seção 5): R$ 28.034,39 das nunca inspecionadas e R$ 52.715,78 das reinspeções |
| Reinspeção sem queda nova continua na fila, no fim | Tirar da fila | O Gerente de Perdas vê as UCs que seguem com consumo baixo depois de uma inspeção sem irregularidade, sem que elas passem à frente das nunca inspecionadas |
| Fator de energia calculado a cada execução | Valor fixo no código | Acompanha os dados e para se sair do esperado |
| `motivos` como `array<string>` | Texto JSON na Gold | O tipo nativo permite checar cada texto; a exportação escreve o JSON |

## 7. Como executar no Databricks

1. **Pré-requisito:** as Silvers e a Gold de GD publicadas.

   ```sql
   SELECT COUNT(*) FROM `v-energy`.silver.tb_inspecoes;            -- esperado: 1389
   SELECT COUNT(*) FROM `v-energy`.silver.tb_medidores;            -- esperado: 51299
   SELECT COUNT(*) FROM `v-energy`.silver.tb_faturas_publicacao;   -- esperado: 2
   SELECT COUNT(*) FROM `v-energy`.gold.gd_uc;                     -- esperado: 3510
   ```

2. Importe o notebook, conecte ao **Serverless** e use **Run all**. O padrão `modo=validar` não grava nada. Para gravar, troque o widget para `modo=publicar` antes de executar. O Workflow do Databricks (#97) vai passar `modo=publicar`.
3. **O que conferir:**
   * todas as linhas `[OK   ]` em `(fontes)`, `(calibração)`, `(candidatas)` e `(antes de gravar)`;
   * `Reconciliação (antes de gravar): 1,389 inspeções | 1,473,112.00 kWh recuperados | 141 UCs na fila`;
   * com `modo=validar`, a linha final `Validação concluída. Nenhum schema ou tabela foi gravado.`;
   * com `modo=publicar`, as linhas `[OK   ]` em `(tabela gravada)` e as duas linhas `Publicada: ...`.

Se uma validação falhar, a mensagem lista cada regra violada com a quantidade de linhas. Uma falha em `(tabela gravada)` já restaurou a Gold anterior.

## 8. Pendências

* **`dim_uc`:** o `id_uc` das duas tabelas é conferido contra a Silver de cadastro, de onde sai a `dim_uc` (#145). A exportação consolidada (#96) confere o `id_uc` das 12 tabelas contra ela.
* **Exportação para o banco local:** fica no passo único de exportação do Job (#96), que escreve `motivos` em JSON.
* **Contrato provisório:** `fila_inspecao.yaml` e `inspecoes_historicas.yaml` estão como `provisorio-nao-aprovado`. Os pontos do score são uma proposta da Gold para a área de Perdas validar.
* **Reincidência:** o consumo das UCs com fraude confirmada continua baixo depois da inspeção (seção 2.7). Pode ser reincidência ou um limite da base sintética; uma fila de reincidência seria uma tabela à parte.
