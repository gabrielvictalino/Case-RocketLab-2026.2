# Dicionário da Gold de perdas e inspeções — produtor pendente

[Índice do dicionário da Gold](decisoes_silver_to_gold.md), domínio 4.

As duas tabelas estão previstas no contrato `0.3.0-provisional`. O notebook
`data-engineering/silver_to_gold/silver-to-gold-perdas.ipynb` ainda não está
integrado na `dev`: a implementação é acompanhada na
[#124](https://github.com/gabrielvictalino/Case-RocketLab-2026.2/issues/124).
Este documento registra o layout e as decisões conhecidas, sem atribuir uma
fórmula de score ou de recuperação a um produtor inexistente.

## 1. Perguntas e fontes

Rafael Coutinho (Perdas) precisa priorizar as UCs suspeitas, ver os sinais que
justificam a inspeção e estimar o potencial de recuperação. O histórico permite
consultar os laudos e a energia já recuperada em campo, inclusive na Visão 360.

Fontes previstas: Silvers de inspeções, leituras, cadastro, medidores e GD. A
Gold `gd_uc` define as UCs que devem ficar fora da fila pelo gate R4. A
[Silver de inspeções](../silver/silver_inspecoes.md) já está implementada:
1.389 inspeções, 871 confirmadas, cobrindo agosto a dezembro de 2025 na base
documentada. Esses números não comprovam uma publicação Gold.

## 2. `inspecoes_historicas` — contrato

**Grão/chave:** uma inspeção / `id_inspecao`. Layout no
[YAML](../../contracts/tabelas/inspecoes_historicas.yaml). A #124 prevê preservar
as inspeções da Silver, com as sete colunas abaixo na ordem do contrato.

| Coluna | Tipo do contrato | Nulo? | Definição / origem prevista |
| --- | --- | :---: | --- |
| `id_inspecao` | text | não | ID único, padrão `IN` + 7 dígitos |
| `id_uc` | text | não | UC inspecionada, padrão `UC` + 6 dígitos, presente em `dim_uc` |
| `data` | date | não | Data efetiva da inspeção, não o mês da aba de origem |
| `inspetor` | text | não | Código padronizado de `INSP-001` a `INSP-040` |
| `resultado` | text | não | `IRREGULARIDADE CONFIRMADA` ou `SEM IRREGULARIDADE` |
| `tipo_irregularidade` | text | sim | Tipo do laudo; nulo sem irregularidade |
| `kwh_recuperado` | numeric(18,2), kWh | não | Energia apurada na inspeção; zero sem irregularidade; não é uma previsão do potencial da fila |

O total de controle previsto no contrato é `SUM(kwh_recuperado)`. A Silver
documenta 1.473.112,00 kWh, preservando os valores extremos. A reconciliação
desse total na Gold depende da entrega do produtor.

### Decisões de limpeza que afetam o histórico

| Decisão já implementada na Silver | Indicador afetado | Efeito |
| --- | --- | --- |
| Datas por formato de cada valor; hífen como `MM-dd-yyyy` | Inspeções e kWh por mês | A aba `dez` contém 107 inspeções de outros meses; agrupar pela aba deslocaria os resultados |
| Resultado padronizado em dois valores | Confirmadas, grupo temporal e flags cadastrais | `CONFIRMADA` vira `IRREGULARIDADE CONFIRMADA`; `NADA CONSTA` vira `SEM IRREGULARIDADE` |
| Vírgula decimal convertida, `kwh_recuperado` decimal, valores extremos preservados | Total de kWh recuperados | Remover ou limitar os 58 extremos reduziria a recuperação registrada |
| Marcadores de ausência de tipo viram nulo | Distribuição por tipo de irregularidade | Ausência não vira categoria de fraude |
| Duplicatas exatas removidas; ID conflitante ou UC ausente bloqueiam a carga | Contagens e somas | Evita duplicar laudos e ligar inspeções a UCs inexistentes |

## 3. `fila_inspecao` — contrato

**Grão/chave:** uma UC candidata / `id_uc`. Layout no
[YAML](../../contracts/tabelas/fila_inspecao.yaml). Todas as colunas são
obrigatórias; os três campos numéricos têm mínimo zero.

| Coluna | Tipo / unidade | Definição | Situação da fórmula |
| --- | --- | --- | --- |
| `id_uc` | text | UC candidata, presente em `dim_uc`, ausente de `gd_uc` | Exclusão integral de GD definida pela R4 |
| `score` | numeric(18,2) | Pontuação para ordenar a propensão à irregularidade | Sinais, pesos, normalização e limiar de seleção pendentes na #124 |
| `motivos` | jsonb | Lista legível de sinais com seus valores, justificando a inclusão | Estrutura e cálculo dos sinais pendentes na #124 |
| `energia_recuperar_kwh` | numeric(18,2), kWh | Potencial estimado caso a irregularidade seja confirmada | Baseline, janela de consumo e regra de estimativa pendentes na #124 |
| `energia_recuperar_reais` | numeric(18,2), R$ | Potencial financeiro estimado da recuperação | Tarifa, tratamento de tributos e arredondamento pendentes na #124 |

A R4 exclui toda UC presente em `gd_uc`; não basta reduzir o score de quem tem
GD. A hipótese de queda de consumo deve distinguir meses bloqueados por troca
de medidor ou sinal não confirmado e leitura estimada, conforme a
[Silver de leituras](../silver/silver_leituras.md). A seleção dos sinais e seu
tratamento ainda precisam ser definidos e justificados pelo produtor.

`SUM(energia_recuperar_kwh)` e `SUM(energia_recuperar_reais)` são os totais de
controle previstos da fila. Não são recuperação já realizada e não têm valor
Gold verificável enquanto o produtor estiver pendente. As fórmulas do gerador
em `contracts/samples/gerar.py` servem a testes sintéticos, não definem o score
nem as estimativas da Gold real.

## 4. Atualização ao integrar a #124

O PR do produtor deve vincular aqui o notebook integrado e definir cada sinal,
seu peso, limiar, janela, tratamento de nulos e regra de arredondamento; registrar
as fórmulas de recuperação em kWh/R$, suas fontes e premissas; e demonstrar
unicidade, integridade com `dim_uc`, exclusão de GD e reconciliação do histórico
com a Silver. Atualize também o domínio 4 do índice com as saídas efetivamente
geradas, incluindo quaisquer tabelas analíticas extras.
