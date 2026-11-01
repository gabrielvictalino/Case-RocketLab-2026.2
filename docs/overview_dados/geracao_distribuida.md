# geracao_distribuida.csv

UCs que possuem micro ou minigeração própria conectada à rede (na prática,
painéis solares), com potência instalada, data de conexão, modalidade de
compensação e energia média injetada.

- Separador: `,` · 3.510 linhas · 5 colunas
- Grão: uma UC com geração distribuída (GD)
- Chave primária e estrangeira: `id_uc` → UC (relação 1:0..1)

## Papel no domínio

- **Sistema de origem**: cadastro de micro e minigeração distribuída.
- **Conceito do case**: *geração distribuída (GD)* é "quando a própria UC
  gera energia, normalmente com painel solar. A energia gerada é abatida do
  consumo faturado".
- **Papel no Grid 360**: responde "se ele tem painel solar" na visão 360 e é
  a **principal explicação da queda de volume** faturado.

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_uc` | string | UC geradora | 3.510 UCs, todas válidas e sem repetição (7,8% da base) |
| `potencia_kwp` | decimal (kWp) | Potência de pico instalada | Mediana 5,87 kWp; ver outliers abaixo |
| `data_conexao` | data | Conexão do sistema à rede | jan/2024 a jun/2026 |
| `modalidade` | categoria | Modalidade de compensação (REN ANEEL 1.000) | `GERACAO NA PROPRIA UC` (3.042), `AUTOCONSUMO REMOTO` (321), `GERACAO COMPARTILHADA` (147) |
| `energia_injetada_kwh_media_mensal` | decimal (kWh) | Média mensal de energia injetada na rede | 30 a 8.250 kWh; mediana 199 kWh |

### Características

- Só há GD em UCs **Residenciais (B1, 89%) e Comerciais (B3, 11%)**.
- Produtividade típica: ~34 kWh injetados por kWp por mês, coerente com a
  irradiação de Pernambuco. Serve de referência para validar `potencia_kwp`.
- Todas as conexões são de 2024 em diante, ou seja, dentro do período das
  leituras: dá para comparar o consumo antes e depois.

## Qualidade

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| `potencia_kwp` com vírgula decimal (`5,53`) | 316 | Trocar vírgula por ponto |
| `potencia_kwp` implausível (> 75 kWp, até 8.994) com injeção típica de ~5 kWp — provavelmente registrado em **Wp** | 35 | Dividir por 1.000 quando > 75 e a razão kWh/kWp for incoerente |

Não há nulos nem duplicatas.

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Diagnóstico da receita | As 3.510 UCs com GD perderam 61% do volume (−11,1 GWh, ≈ −R$ 7,7 mi a preços do primeiro ano) — a maior causa isolada da queda de volume, em Residencial e Comercial |
| Visão 360 (Atendimento) | Potência, modalidade e data de conexão; explica por que o consumo da UC caiu ou oscila |
| Fila de inspeção (Perdas) | **Excluir ou descontar a injeção declarada**: GD gera queda de consumo legítima e inundaria a fila de falsos positivos |
| Agente de IA | "Painel solar", "energia solar"; exemplo da Diretora de Tecnologia: em Olinda, 327 das 328 UCs com GD tiveram queda > 30% após a conexão |

Correlações:

- Após `data_conexao`, o consumo mediano das leituras cai de 290 para
  92 kWh/mês. A queda mensal equivale a ~91% de
  `energia_injetada_kwh_media_mensal` (correlação 0,86).
- Antes da conexão, essas UCs consumiam ~2× mais que as demais da mesma
  classe: GD é adotada pelos maiores consumidores, o que amplia o impacto na
  receita.
- As conexões desaceleram (1.038 no 1º semestre de 2024, 361 no 1º semestre
  de 2026), mas o estoque instalado (~31,9 MWp) continua reduzindo o volume.
- **Sem vínculo com atendimentos de GD**: só 7,8% dos atendimentos de
  assunto `GERACAO DISTRIBUIDA` vêm de UCs deste arquivo — exatamente a
  participação dessas UCs na base. O assunto do atendimento foi distribuído
  sem relação com a UC ter ou não GD; não use esse cruzamento como evidência.
