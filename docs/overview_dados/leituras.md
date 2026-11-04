# leituras/leituras_AAAA.csv

Leituras mensais do medidor de cada UC: valor do registrador no mês anterior
e no atual e o consumo resultante em kWh. É a principal fonte de consumo e a
base de cálculo das faturas.

- 5 arquivos particionados por ano de `mes_referencia`: 2022 (jul–dez),
  2023, 2024, 2025, 2026 (jan–jun). O ano do arquivo sempre bate com o
  `mes_referencia`.
- Separador: `,` · 2.182.468 linhas no total · 9 colunas
- Grão: uma leitura de uma UC em um mês de referência
- Chave primária: `id_leitura` · Chave natural: `(id_uc, mes_referencia)`
- Chaves estrangeiras: `id_uc` → UC, `id_medidor` → medidor

| Arquivo | Linhas |
|---|---:|
| `leituras_2022.csv` | 271.744 |
| `leituras_2023.csv` | 544.546 |
| `leituras_2024.csv` | 545.652 |
| `leituras_2025.csv` | 546.908 |
| `leituras_2026.csv` | 273.618 |

## Papel no domínio

- **Sistema de origem**: medição.
- **Conceito do case**: o consumo de energia por *competência* — "o mês de
  referência de uma leitura ou fatura". `mes_referencia` é a competência e
  faz a ponte com o faturamento.
- **Papel no Grid 360**: é a medida de **quantidade** do negócio. O "volume de
  energia faturada" que caiu quase 4% na fala do Diretor Comercial é a soma
  de `consumo_kwh`. Também sustenta o histórico de consumo do atendente e o
  principal sinal da equipe de perdas.
- Em UCs com geração distribuída, o consumo medido é **líquido**: o case
  lembra que "a energia gerada é abatida do consumo faturado".

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_leitura` | string | Identificador da leitura | `LT` + 9 dígitos; `LTX…` são registros espúrios |
| `id_uc` | string | UC lida | 45.000 UCs, todas válidas |
| `id_medidor` | string | Medidor que registrou | `MD9xxxxxx` = medidor inexistente |
| `data_leitura` | data | Dia em que a leitura foi feita | Sempre dentro do `mes_referencia` |
| `mes_referencia` | ano-mês | Competência | `AAAA-MM`, 2022-07 a 2026-06 (48 meses) |
| `leitura_anterior` | inteiro | Registrador no fim do mês anterior | Igual à `leitura_atual` do mês anterior em 98,5% dos casos |
| `leitura_atual` | inteiro | Registrador neste mês | Acumulado, sempre crescente |
| `consumo_kwh` | inteiro | Energia consumida no mês | ≈ `leitura_atual − leitura_anterior` |
| `tipo_leitura` | categoria | Origem da leitura | `REAL` (82%) ou `ESTIMADA` (18%) |

### Comportamento do consumo

- Mediana por classe (kWh/mês): Residencial 150 · Rural 249 · Comercial 645 ·
  Poder Público 1.145 · Industrial 5.731. Os 10.727 valores acima de
  10.000 kWh são quase todos de UCs industriais (subgrupo `A4`): são
  legítimos, não outliers a remover.
- **Sazonalidade**: o 1º semestre consome ~35% mais que o 2º (verão).
- UCs com geração distribuída: consumo mediano cai de 290 para 92 kWh após a
  conexão — o campo registra o consumo **líquido** da rede.
- Leituras estimadas: ~19% até 2025, caindo para 14% em 2026 (coincide com
  a troca para medidores inteligentes).

## Qualidade

Contagens após remover as duplicatas exatas.

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| Duplicatas exatas (mesmo `id_leitura`) | 21.523 | `DISTINCT` |
| Leituras `LTX…` com `id_medidor` inexistente (`MD9…`), cópia de uma leitura legítima da mesma UC/mês | 8.609 | Descartar (falha de FK + duplicidade de chave natural) |
| `consumo_kwh` negativo por **troca de medidor**: `leitura_anterior` é do medidor antigo e `leitura_atual` do novo (que começa perto de zero) | ~6.250 | Consumo real desconhecido; marcar e excluir de médias ou estimar pela média da UC |
| `consumo_kwh` negativo com **sinal invertido** (valor absoluto = `atual − anterior`; gravado como decimal, ex. `-101.0`) | ~1.700 | Inverter o sinal |
| `consumo_kwh` negativo sem `leitura_anterior` | ~110 | Avaliar caso a caso |
| `consumo_kwh` diverge de `atual − anterior` em ±1 kWh (arredondamento) | 521.616 | Tolerar ±1; usar `consumo_kwh` como fonte de verdade |
| `leitura_anterior` ausente: vazio, `N/A`, `NULL` ou `-1` (~8 mil de cada) | ~32.400 | Nulo; pode ser reconstruída da leitura do mês anterior |
| `data_leitura` fora do ISO: `DD/MM/AAAA`, `DD.MM.AAAA`, **`MM-DD-AAAA`** (~86 mil cada) | ~259.000 | Parse pelo separador |

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Diagnóstico da receita | **Efeito-volume**: o volume cai 4,0% entre o primeiro ano e os últimos 12 meses. Toda a queda vem de UCs com GD (−61%) e com fraude (−51%); as demais crescem 2,3% |
| Visão 360 / "conta alta" | Consumo dos últimos meses × mesmo mês do ano anterior (`mes_referencia − 12`), com marcação de leitura estimada e de troca de medidor. Em ~80% das reclamações de valor alto o consumo **não** subiu mais de 10% |
| Fila de inspeção | **Queda de consumo** em relação ao histórico da própria UC (AUC 0,92) e **proporção de leituras estimadas** (41% nas fraudadoras × 16–21% nas demais). A queda começa ~4–5 meses antes da inspeção e serve para estimar a energia a recuperar |
| Agente de IA | Perguntas sobre "consumo"; exemplo da Diretora de Tecnologia: UCs com painel solar com queda > 30% |
| Integridade referencial | Junção 1:1 com faturas por `(id_uc, mes_referencia)`; remoção das 8.609 leituras com medidor inexistente |

Decisões de limpeza que mudam métricas: o tratamento dos meses de troca de
medidor (volume −4,0% com imputação × −5,1% sem), a correção do sinal
invertido e a remoção das duplicatas devem constar no dicionário da Gold.

Outros comportamentos relevantes:

- A sazonalidade (1º semestre ~35% acima do 2º) exige comparar sempre o
  mesmo período do ano anterior, nunca o mês anterior.
- A queda de leituras estimadas em 2026 coincide com a troca por medidores
  inteligentes.
