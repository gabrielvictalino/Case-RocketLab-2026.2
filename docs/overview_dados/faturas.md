# faturas.csv

Faturas mensais emitidas para cada UC: valor da energia, tributos, bandeira
tarifária, vencimento, pagamento e situação. É a fonte de faturamento e de
inadimplência.

- Separador: **`;`** (diferente dos demais CSVs) · 2.184.623 linhas · 11 colunas
- Grão: uma fatura de uma UC em um mês de referência
- Chave primária: `id_fatura` · Chave natural: `(id_uc, mes_referencia)`
- Chave estrangeira: `id_uc` → UC

## Papel no domínio

- **Sistema de origem**: faturamento. É o CSV "com ponto e vírgula" citado
  pela Diretora de Tecnologia.
- **Conceitos do case**: *competência* (a fatura 03/2025 cobra o consumo de
  março, mesmo paga em abril) e *bandeira tarifária* — acréscimo definido mês
  a mês pela ANEEL que "muda a receita sem mudar o consumo".
- **Papel no Grid 360**: é a medida de **receita e preço**. A receita que
  "subiu só 8%" é a soma de `valor_total`. Também mostra as faturas em aberto
  do cliente.

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_fatura` | string | Identificador da fatura | `FT` + 9 dígitos; `FTX…` são registros sem UC válida |
| `id_uc` | string | UC faturada | `UC` + 6 dígitos; `UC9` + 6 dígitos = UC inexistente |
| `mes_referencia` | ano-mês | Competência faturada | `AAAA-MM`, 2022-07 a 2026-06 |
| `data_emissao` | data | Emissão da fatura | No próprio `mes_referencia` (99,5%) ou no mês seguinte |
| `valor_energia` | decimal (R$) | Valor da energia consumida | R$ 4,78 a R$ 35.810,60; mediana R$ 97 |
| `tributos` | decimal (R$) | Impostos e encargos | Sempre `valor_energia / 3` (25% do total) |
| `bandeira_tarifaria` | categoria | Bandeira do mês | `Verde`, `Amarela`, `Vermelha P1`, `Vermelha P2` |
| `valor_total` | decimal (R$) | Total a pagar | `valor_energia + tributos` (exato após normalizar) |
| `data_vencimento` | data | Vencimento | Sempre `data_emissao + 12 dias` |
| `data_pagamento` | data | Data do pagamento | Nula ou `9999-12-31` se não paga |
| `status` | categoria | Situação | `PAGA` (2.009.453), `EM ABERTO` (175.168) |

### Regras de negócio observadas

- **Valor da energia ≈ consumo × tarifa**. Juntando com as leituras do mesmo
  mês, a correlação entre `consumo_kwh` e `valor_energia` é **0,996**. A
  tarifa implícita (R$/kWh) mediana no período varia com:
  - bandeira: Verde 0,568 · Amarela 0,598 · Vermelha P1 0,623 · Vermelha P2 0,656;
  - classe: Industrial (A4) 0,505 · Residencial (B1) 0,569 · demais 0,603.
- **Modelo tarifário implícito**: `valor_energia = consumo × (tarifa base da
  classe vigente no mês + adicional da bandeira)`, com erro médio de 0,2%.
  O adicional é igual para todas as classes: amarela +R$ 0,0189/kWh,
  vermelha P1 +R$ 0,0446/kWh, vermelha P2 +R$ 0,0788/kWh. A tarifa base muda
  nos reajustes de maio (mais um ajuste residencial em jan/2026):

  | Classe | jul/2022 | mai/2023 | mai/2024 | mai/2025 | jan/2026 | mai/2026 |
  |---|---:|---:|---:|---:|---:|---:|
  | Residencial | 0,5305 | 0,5691 | 0,5678 | 0,5784 | 0,5856 | 0,5863 |
  | Comercial / Poder Público | 0,5589 | 0,6029 | 0,6007 | 0,6436 | 0,6436 | 0,6645 |
  | Rural | 0,5217 | 0,6029 | 0,6007 | 0,6435 | 0,6436 | 0,6645 |
  | Industrial | 0,4666 | 0,5054 | 0,5558 | 0,4867 | 0,4868 | 0,4615 |

  Com o modelo, a Gold pode separar exatamente o efeito-reajuste do
  efeito-bandeira, mesmo sem uma tabela de tarifas na base.
- **Bandeira é a mesma para todas as UCs no mês** (é nacional), então funciona
  como atributo do calendário:

  | Período | Bandeira |
  |---|---|
  | 2022-07 a 2024-06 | Verde |
  | 2024-07 | Amarela |
  | 2024-08 | Verde |
  | 2024-09 | Vermelha P1 |
  | 2024-10 | Vermelha P2 |
  | 2024-11 | Amarela |
  | 2024-12 a 2025-04 | Verde |
  | 2025-05 | Amarela |
  | 2025-06 a 2025-07 | Vermelha P1 |
  | 2025-08 a 2025-09 | Vermelha P2 |
  | 2025-10 a 2025-11 | Vermelha P1 |
  | 2025-12 | Amarela |
  | 2026-01 a 2026-04 | Verde |
  | 2026-05 a 2026-06 | Amarela |

- **Pagamento**: entre 4 dias antes e 25 dias depois do vencimento; 77% das
  faturas pagas foram quitadas com atraso (mediana: 11 dias após o vencimento).
- **Em aberto**: ~8% das faturas de todos os meses, inclusive os mais
  antigos (~3.600–3.700 por mês) — inadimplência persistente, não apenas
  faturas recentes ainda não vencidas.
- UCs presentes em todo o período têm 48 faturas; o volume mensal cresce
  de 45.301 para 45.652 conforme novas UCs são ligadas.

## Qualidade

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| Cabeçalho repetido no meio do arquivo | 2 | Descartar linhas onde `id_fatura = 'id_fatura'` |
| Faturas `FTX…` de UCs inexistentes (`UC9xxxxxx`, 31.705 UCs distintas) | 32.285 | Descartar ou isolar em quarentena (falha de FK) |
| Faturas `FTX…` duplicadas para a mesma UC/mês, com valores diferentes | 22 | Descartadas junto com as órfãs |
| `valor_total` no formato monetário brasileiro (`R$ 1.234,56`) | 196.622 | Remover `R$`, ponto de milhar e trocar vírgula por ponto |
| `data_emissao` fora do ISO: `DD/MM/AAAA` (61.291), `DD.MM.AAAA` (61.252), **`MM-DD-AAAA`** (60.818) | 183.361 | Parse pelo separador |
| `data_pagamento = 9999-12-31` em fatura em aberto (sentinela) | 61.333 | Nulo |

Para UCs válidas, a chave natural `(id_uc, mes_referencia)` é única.

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Diagnóstico da receita | **Efeito-preço**: dos +R$ 12,6 mi de variação, +R$ 11,3 mi vêm de reajuste tarifário e +R$ 7,4 mi de bandeiras, contra −R$ 6,3 mi de volume. A tarifa base residencial subiu 10,5%, exatamente o valor citado no case. Detalhes em [../diagnostico_receita.md](../diagnostico_receita.md) |
| Indicadores da diretoria | Receita faturada × arrecadada; inadimplência (~5,5% do valor faturado, estável — não explica a variação) |
| Visão 360 / "conta alta" | Faturas em aberto, dias de atraso e **bandeira de cada mês**, para o atendente separar aumento de consumo, de bandeira e de tarifa |
| Agente de IA | "Conta de luz", "conta atrasada", "bandeira vermelha"; pergunta de exemplo: "Quanto a receita comercial cresceu em Jaboatão?" (resposta: caiu 5,1% no último ano) |
| Integridade referencial | Remover as 32.285 faturas de UCs inexistentes, que inflariam a receita em R$ 10,2 mi (+1,5%) |

Correlações com outras fontes:

- `valor_energia` ≈ `consumo_kwh` × tarifa da classe × fator da bandeira
  (correlação 0,996). Por isso a tarifa vigente pode ser derivada dos meses de
  bandeira verde, mesmo sem uma tabela de tarifas.
- A bandeira é a mesma para todas as UCs no mês: é um atributo do calendário,
  útil como dimensão de tempo na Gold.
- UCs com fraude confirmada **não** diferem na inadimplência (7,5% × 8,0% das
  faturas em aberto).
