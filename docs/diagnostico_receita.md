# Diagnóstico da variação de receita — V-Energy

Resposta à pergunta que originou o projeto V-Energy Grid 360:

> "A base de clientes cresceu, e a tarifa residencial acumulou reajuste
> homologado de 10,5% desde meados de 2022. Mesmo assim, comparando os últimos
> 12 meses com o primeiro ano da nossa base, o volume de energia faturada caiu
> quase 4% e a receita subiu só 8%. Ninguém nesta mesa sabe explicar por quê."
> — Henrique Duarte, Diretor Comercial

## Resposta curta

**A receita só subiu porque o preço subiu, e uma parte dessa alta é
temporária. O volume caiu porque energia deixou de passar pelo medidor da
V-Energy, e não porque os clientes consomem menos.**

1. **Preço (+R$ 18,8 mi)**: os reajustes tarifários somaram +R$ 11,3 mi e as
   bandeiras amarela e vermelha, +R$ 7,4 mi. As bandeiras não se repetem num
   ano de bandeira verde.
2. **Volume (−R$ 6,3 mi)**: a queda de 4,0% vem de dois grupos que somam 10%
   das UCs:
   - **3.510 UCs com painel solar** (geração distribuída): −61% de volume
     faturado. O consumo continua, mas é suprido pela própria geração.
   - **871 UCs com fraude confirmada**, concentradas em 4 bairros: −51% de
     volume medido.
   - As outras ~40.600 UCs **cresceram 2,3%**.
3. **Tendência**: no último ano (jul/25–jun/26 contra jul/24–jun/25) a receita
   já **caiu 1,25%**. Ao efeito da GD somaram-se a perda das fraudes e cortes
   na tarifa industrial (−12,4% em mai/2025).

Ordem de grandeza das alavancas: **~R$ 3 mi** de recuperação em fraudes
(regularização das UCs + cobrança da energia recuperada) e **~R$ 1,7 mi/ano**
com redução da inadimplência. Há ainda **~R$ 8,7 mi/ano** de receita que a
GD já retira da base, que pede revisão da estratégia comercial e das
projeções, e não uma ação de recuperação.

## 1. Escopo, definições e base de dados

| Item | Definição |
|---|---|
| Primeiro ano (A1) | Competências jul/2022 a jun/2023 |
| Últimos 12 meses (A4) | Competências jul/2025 a jun/2026 |
| Receita | Soma de `valor_total` das faturas (energia + tributos), por competência |
| Volume faturado | Soma de `consumo_kwh` das leituras com fatura na mesma competência |
| Base | 45.000 UCs válidas, após remover registros de teste, duplicatas e faturas/leituras órfãs |

As regras de limpeza estão em [overview_dados/qualidade_dados.md](overview_dados/qualidade_dados.md).
Duas delas mudam os números deste diagnóstico:

- **Faturas órfãs**: 32.285 faturas de UCs inexistentes (R$ 10,2 mi) foram
  excluídas. Mantidas, inflariam a receita em 1,5%.
- **Troca de medidor**: nos ~6.250 meses em que o medidor foi trocado
  (set/2025–mar/2026), o consumo registrado é inválido e foi estimado pela
  mediana da própria UC. Sem esse tratamento, a queda de volume aparece como
  −5,1%, e não −4,0%.

> Os números foram calculados na análise exploratória dos dados brutos.
> Devem ser reconferidos nas tabelas Gold do pipeline antes da apresentação
> final; a ordem de grandeza e as conclusões não dependem de ajustes finos.

## 2. Os números

| Ano de competência | Receita | Var. | Volume | Var. | Preço médio (R$/kWh, com tributos) | Meses de bandeira não verde |
|---|---:|---:|---:|---:|---:|---:|
| A1 · jul/22–jun/23 | R$ 157,1 mi | — | 227,1 GWh | — | 0,692 | 0 |
| A2 · jul/23–jun/24 | R$ 167,9 mi | +6,9% | 226,4 GWh | −0,3% | 0,742 | 0 |
| A3 · jul/24–jun/25 | R$ 171,8 mi | +2,4% | 220,0 GWh | −2,8% | 0,781 | 6 |
| A4 · jul/25–jun/26 | R$ 169,7 mi | **−1,25%** | 217,9 GWh | −0,9% | 0,779 | 8 |
| **A4 vs A1** | | **+8,0%** | | **−4,0%** | **+12,5%** | |

Os dados confirmam os números da diretoria: volume −4,0% e receita +8,0%. O
número de UCs faturadas cresceu 0,6% (44.741 → 45.000), e todas seguem ativas:
não houve perda de clientes.

## 3. Quanto foi preço e quanto foi volume

A tarifa de cada mês é explicada com erro médio de 0,2% por um modelo simples:
**tarifa = tarifa base da classe (bandeira verde) + adicional da bandeira**.
O adicional é o mesmo para todas as classes: amarela +R$ 0,0189/kWh,
vermelha P1 +R$ 0,0446/kWh, vermelha P2 +R$ 0,0788/kWh (sem tributos). Isso
permite separar o efeito do reajuste do efeito da bandeira:

| Efeito | A1 → A4 | A3 → A4 (último ano) | Como foi calculado |
|---|---:|---:|---|
| **Volume** | **−R$ 6,3 mi** | −R$ 1,6 mi | (kWh novo − kWh antigo) × preço médio antigo |
| **Reajuste tarifário** | **+R$ 11,3 mi** | −R$ 3,2 mi | kWh novo × (tarifa base nova − tarifa base antiga) |
| **Bandeiras** | **+R$ 7,4 mi** | +R$ 2,5 mi | kWh novo × (adicional médio novo − adicional médio antigo) |
| Resíduo (mix) | +R$ 0,1 mi | +R$ 0,1 mi | |
| **Variação da receita** | **+R$ 12,6 mi** | **−R$ 2,1 mi** | |

Leitura para a diretoria:

- **Sem a queda de volume**, a receita teria subido ~12%, em linha com o
  reajuste.
- **Sem as bandeiras**, a receita dos últimos 12 meses seria de
  R$ 162,1 mi: apenas **+3,2%** sobre o primeiro ano. Em A1 todos os meses
  foram de bandeira verde; em A4, 8 dos 12 meses tiveram bandeira amarela ou
  vermelha.

### Reajustes por classe

O reajuste é aplicado em maio de cada ano (com um ajuste extra da tarifa
residencial em jan/2026). O acumulado difere muito entre as classes:

| Classe (subgrupo) | Tarifa base jul/2022 | Tarifa base jun/2026 | Acumulado |
|---|---:|---:|---:|
| Residencial (B1) | R$ 0,5305 | R$ 0,5863 | **+10,5%** (o valor citado pelo diretor) |
| Comercial e Poder Público (B3) | R$ 0,5589 | R$ 0,6645 | +18,9% |
| Rural (B2) | R$ 0,5217 | R$ 0,6646 | +27,4% |
| Industrial (A4) | R$ 0,4666 | R$ 0,4615 | **−1,1%** |

A tarifa industrial subiu 8,3% (mai/2023) e 10,0% (mai/2024), mas **caiu
12,4% em mai/2025 e mais 5,2% em mai/2026**. Isso explica por que a receita
industrial caiu 8,6% no último ano (−R$ 5,6 mi), mesmo com volume estável.

## 4. Onde e por que o volume caiu

| Grupo de UCs | UCs | Volume A1 | Volume A4 | Variação | Receita A1 → A4 |
|---|---:|---:|---:|---:|---:|
| Com geração distribuída (GD) | 3.510 | 18,3 GWh | 7,2 GWh | **−61%** | R$ 13,4 mi → R$ 6,0 mi (−55%) |
| Com fraude confirmada | 871 | 5,1 GWh | 2,5 GWh | **−51%** | R$ 3,8 mi → R$ 2,1 mi (−43%) |
| Demais | ~40.600 | 203,7 GWh | 208,3 GWh | **+2,3%** | R$ 140,0 mi → R$ 161,5 mi (+15%) |
| **Total** | 45.000 | 227,1 GWh | 217,9 GWh | **−4,0%** | +8,0% |

Sem GD e sem fraude, o volume teria **crescido 2,0%**.

### 4.1 Geração distribuída: a principal causa (≈ 80% da perda de volume)

- **O que acontece**: o painel solar abate a energia gerada do consumo
  faturado. Depois da conexão, o consumo faturado mediano dessas UCs cai de
  290 para 92 kWh/mês. A queda equivale a ~91% da energia injetada
  declarada (correlação 0,86).
- **Quem adota**: residenciais (89%) e comerciais (11%) que consumiam **o
  dobro** da média da sua classe (residencial 273 vs 149 kWh/mês; comercial
  1.480 vs 628). São justamente os clientes de maior receita.
- **Ritmo**: todas as 3.510 conexões ocorreram a partir de jan/2024. O ritmo
  vem caindo (547 no 1º trimestre de 2024, 154 no 2º trimestre de 2026), mas o
  estoque instalado (~31,9 MWp) já tira **~11 GWh/ano** do faturamento:
  **≈ R$ 8,7 mi/ano** aos preços atuais.
- **Efeito já contratado para o próximo ano**: as 916 UCs conectadas durante
  A4 ficaram em média só 7 meses conectadas no período. No ano cheio, retiram
  mais ~1,2 GWh (≈ −R$ 0,9 mi), mesmo sem nenhuma conexão nova.
- **Onde**: em todos os municípios. A GD responde por cerca de 1/3 da perda
  residencial nos bairros mais afetados e pela maior parte da queda comercial
  (−4,7 GWh dos −5,3 GWh da classe).
- **Como é faturada**: nos dados, a fatura de uma UC com GD aplica a mesma
  tarifa das demais sobre o consumo líquido, sem valor mínimo aparente (15%
  das faturas após a conexão são de até 50 kWh).

### 4.2 Fraude: a segunda causa (≈ 20% da perda de volume)

- **Onde**: 96% das 871 fraudes confirmadas estão em **4 bairros** —
  **Iputinga** e **Macaxeira** (Recife), **Jardim Jordão** e **Prazeres**
  (Jaboatão). São os bairros residenciais que mais perderam volume:

  | Bairro | Volume residencial A1 → A4 | Fraude | GD | Demais UCs |
  |---|---:|---:|---:|---:|
  | Iputinga (Recife) | −499 MWh (−22%) | −331 | −197 | +29 |
  | Jardim Jordão (Jaboatão) | −440 MWh (−22%) | −303 | −163 | +26 |
  | Macaxeira (Recife) | −234 MWh (−22%) | −169 | −69 | +4 |
  | Prazeres (Jaboatão) | −215 MWh (−19%) | −144 | −86 | +15 |

- **Quando**: o consumo dessas UCs caiu para ~30% do normal em
  **mai–jun/2025**, ~4–5 meses antes das inspeções (ago–dez/2025). Depois da
  inspeção, voltou a apenas ~50% do histórico: **a regularização não
  restabeleceu o faturamento**.
- **Quem**: UCs que consumiam ~1,7× a média, com 41% das leituras
  estimadas (contra ~18% nas demais), majoritariamente com medidor
  eletromecânico. Comercial tem 84% de acerto nas inspeções.
- **Impacto**: −2,6 GWh/ano, **≈ R$ 2,0 mi/ano** aos preços atuais.
- **Efeito em Jaboatão**: é o município com maior queda de volume (−6,8%) e
  menor alta de receita (+4,8%). A receita comercial de Jaboatão caiu 2,1% em
  relação ao primeiro ano e 5,1% no último ano.

### 4.3 O restante da base cresce

As ~40.600 UCs sem GD e sem fraude aumentaram o consumo em 2,3% (+4,6 GWh) e a
receita em 15%. Indústria, rural e poder público têm volume estável ou em
alta. Não há retração de demanda.

## 5. O que não explica a variação

| Hipótese | Evidência | Conclusão |
|---|---|---|
| Perda de clientes | 45.000 UCs ativas; base +0,6% | Não explica |
| Inadimplência | Valor em aberto estável: 5,5% (A1) → 5,6% (A4) do faturado | Não explica a receita faturada (é alavanca de caixa, ver R4) |
| Retração do consumo | UCs sem GD e sem fraude: +2,3% | Não explica |
| Sazonalidade | Os dois períodos comparados têm os mesmos 12 meses do calendário | Neutra |
| Eventos de rede (jul/2025) | O consumo de jul/2025 é igual ao de jul/2024, inclusive nas UCs que tiveram interrupção no mês | Não explica |

## 6. Recomendações

| # | Recomendação | Evidência | Ordem de grandeza | Prazo |
|---|---|---|---|---|
| R1 | **Reinspecionar e regularizar as 871 UCs fraudadoras**, cobrando a energia recuperada | Consumo ainda em ~50% do histórico após a inspeção; 1,47 GWh de `kwh_recuperado` registrado | **≈ R$ 2,0 mi/ano** de faturamento recorrente + **≈ R$ 1,1 mi** de recuperação pontual | Curto (0–6 meses) |
| R2 | **Fila de inspeção priorizada pelo Grid 360**: queda de consumo vs histórico da própria UC, excluindo GD, combinada com leituras estimadas, bairro e tipo de medidor | Nas inspeções já feitas, a fila teria acertado 92%, contra 62,7% hoje. A fraude aparece nos dados 4–5 meses antes da inspeção | Antecipar a detecção de 4–5 para 1–2 meses reduz em ~60% a perda por caso (~R$ 200/mês por UC fraudadora). Hoje há 100–170 UCs suspeitas ainda não inspecionadas | Curto |
| R3 | **Substituir os medidores eletromecânicos nos 4 bairros críticos**, aproveitando o programa de medidores inteligentes em curso | Nesses bairros, 92% das inspeções em UCs com eletromecânico encontraram fraude; o smart meter reduz leituras estimadas | Protege o ≈ R$ 2,0 mi/ano recuperado em R1 contra reincidência | Médio (6–12 meses) |
| R4 | **Ação de cobrança focada em Residencial e Poder Público** | R$ 9,5 mi em aberto em A4 (5,6% do faturado); 8,5% em Residencial e 9,7% em Poder Público | Cada 1 p.p. de redução ≈ **R$ 1,7 mi/ano** em caixa | Curto |
| R5 | **Incorporar a GD às projeções de receita e à estratégia comercial**: modelar a perda por nova conexão (~R$ 2,5 mil/ano por UC) e validar com a área regulatória a aplicação dos componentes tarifários previstos para micro e minigeração (Lei 14.300/2022) | GD retira ≈ R$ 8,7 mi/ano; +R$ 0,9 mi já contratado para o próximo ano; nos dados, a GD é faturada só sobre o consumo líquido | Tamanho do problema: ≈ R$ 8,7 mi/ano. Potencial regulatório a quantificar | Médio |
| R6 | **Não tratar bandeira como crescimento**: orçar com bandeira verde e acompanhar o efeito-bandeira separado no painel da diretoria | +R$ 7,4 mi de bandeiras em A4; sem elas, a receita cresceria 3,2% | Risco de −R$ 7,4 mi (−4,4%) num ano de bandeira verde | Imediato |
| R7 | **Projetar o efeito do corte da tarifa industrial** | −12,4% (mai/2025) e −5,2% (mai/2026) na tarifa base A4 | ≈ −R$ 2,5 mi adicionais no próximo ano (efeito anual do corte de mai/2026) | Imediato |

Observação sobre R6: na regulação do setor, a arrecadação das bandeiras
custeia o aumento do custo de geração. Por isso, mesmo quando ocorre, ela não
deve ser lida como melhora de desempenho comercial.

### Prioridade

1. **R1 + R2 + R3** atacam a única causa de queda de volume que é
   recuperável: ≈ R$ 3 mi no primeiro ano e proteção de ≈ R$ 2 mi/ano.
2. **R6 + R7** evitam que a diretoria leia como crescimento uma receita que
   tende a cair: a soma das bandeiras e do corte industrial pode retirar
   ≈ R$ 10 mi num ano de bandeira verde.
3. **R5** responde à causa estrutural (GD), que não se reverte e cresce a
   cada nova conexão.

## 7. Como o Grid 360 acompanha este diagnóstico

| Pergunta de acompanhamento | Onde no Grid 360 |
|---|---|
| Quanto da variação de receita foi volume, reajuste e bandeira? | Painel de receita com a decomposição do período filtrado, por município, bairro e classe |
| O volume perdido por GD e por fraude está aumentando? | Série mensal de volume por grupo (GD / fraude / demais) |
| As UCs regularizadas voltaram a consumir? | Visão 360 da UC e fila de perdas com o status pós-inspeção |
| Quais UCs inspecionar agora? | Fila de inspeção priorizada, com motivo e energia estimada a recuperar |
| Quanto falta receber? | Indicador de inadimplência por classe e município |

O mapeamento completo entre dados, requisitos e perguntas está em
[overview_dados/perguntas_negocio.md](overview_dados/perguntas_negocio.md).

## 8. Limitações e premissas

- **Fraude**: só as UCs inspecionadas (ago–dez/2025) são classificadas como
  fraudadoras. Pode haver fraude não detectada; a análise de quedas de
  consumo indica um volume residual pequeno (100–170 UCs suspeitas).
- **Tarifa**: não há tabela de tarifas na base. A tarifa foi derivada de
  `valor_energia / consumo`, com erro médio de 0,2% no modelo base + bandeira.
- **GD**: a energia injetada é uma média mensal declarada, e não uma série;
  o impacto foi medido pela queda de consumo antes e depois da conexão.
- **Troca de medidor**: o consumo dos meses de troca foi estimado. A
  conclusão sobre o volume (−4,0%) depende desse tratamento.
- **Valores monetários** em reais correntes, sem correção pela inflação.
- O impacto das recomendações é estimado por ordem de grandeza, com os preços
  médios dos últimos 12 meses (R$ 0,78/kWh com tributos).
