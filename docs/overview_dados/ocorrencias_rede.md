# ocorrencias_rede.csv

Ocorrências registradas na rede de distribuição (faltas de energia,
oscilações, fios partidos etc.), com alimentador, UC de referência, causa,
horários de abertura/encerramento e duração.

- Separador: `,` · 180.000 linhas · 8 colunas
- Grão: uma ocorrência
- Chave primária: `id_ocorrencia`
- Chaves estrangeiras: `id_uc` → UC; `alimentador` → dimensão alimentador

## Papel no domínio

- **Sistema de origem**: operação da rede (o "terceiro sistema" do case).
- **Conceito do case**: interrupções de fornecimento por alimentador, base
  dos indicadores **DEC e FEC** cobrados pela ANEEL. O case define que
  "cada registro de ocorrência corresponde a uma unidade consumidora
  interrompida" e que os valores servem para comparar alimentadores e
  períodos entre si, não com os limites regulatórios reais.
- **Papel no Grid 360**: continuidade do serviço para a Gerente de Operação e
  resposta para "se a rua dele teve falta de luz" na visão 360.

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_ocorrencia` | string | Identificador | `OC` + 8 dígitos, sem repetição |
| `alimentador` | string | Circuito afetado | 122 alimentadores (todos os da base) |
| `id_uc` | string | UC que originou/registrou a ocorrência | 41.512 UCs distintas, todas válidas |
| `tipo` | categoria | Tipo de ocorrência | `FALTA DE ENERGIA` (68%), `DANO EM EQUIPAMENTO`, `OSCILACAO`, `SOBRECARGA`, `FIO PARTIDO` (~8% cada) |
| `causa` | categoria | Causa apurada | `CLIMATICA` (24%), `NAO IDENTIFICADA`, `SOBRECARGA`, `VEGETACAO`, `TERCEIROS`, `FALHA DE EQUIPAMENTO` (~15% cada) |
| `data_abertura` | data-hora | Início | `AAAA-MM-DD HH:MM:SS`, jul/2022 a jun/2026 |
| `data_encerramento` | data-hora | Fim | Sempre posterior à abertura |
| `duracao_min` | inteiro (min) | Duração | 5 a 2.880 min (48 h); mediana 72 min |

### Características

- `alimentador` da ocorrência é **sempre** o mesmo alimentador cadastrado
  para a `id_uc` — campo redundante, útil para agregar por região.
- `duracao_min` é exatamente `data_encerramento − data_abertura` em todos
  os registros com valor numérico.
- Ocorrências de causa `CLIMATICA` duram mais (mediana 101 min contra ~66 min
  das demais).
- Volume estável (~3.350/mês), com picos:
  - **jul/2025: 17.844 ocorrências (×5)**, todas `FALTA DE ENERGIA`, 97% com
    causa `CLIMATICA`, concentradas em Recife, São Lourenço da Mata e
    Jaboatão, espalhadas pelo mês todo — um evento climático prolongado;
  - nov/2025 e fev/2026: ~5.300 (+60%), com tipos e causas na proporção normal.
- Alimentador mais afetado: `ALM-REC-008` (8.211 ocorrências, ~6× a média).

## Qualidade

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| `duracao_min` com unidade no texto (`"23 min"`) | 16.200 | Extrair o número, ou recalcular pelas datas |
| `causa` ausente: vazio (1.356), `-` (1.363), `N/A` (1.341), `NULL` (1.340) | 5.400 | Nulo (ou `NAO IDENTIFICADA`) |

Não há duplicatas nem problemas de formato de data.

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| DEC/FEC por alimentador (Operação; requisito de engenharia de dados) | DEC = Σ horas ÷ UCs do alimentador; FEC = nº de ocorrências ÷ UCs do alimentador. Sistema: DEC ~1,5 h e FEC ~0,9 em 2023–2024; 3,39 h / 1,27 em 2025 |
| Identificar os piores alimentadores | Ranking por DEC/FEC complementado pelo **CHI** (horas × UCs) e pela causa: cada alimentador tem ~300–400 ocorrências/ano, independentemente do tamanho, e os de poucas UCs dominam o ranking de DEC |
| Visão 360 (Atendimento) | Ocorrências do **mesmo alimentador** da UC nos últimos dias ("a rua dele teve falta de luz") |
| Agente de IA | "Falta de luz", "apagão" (evento na rede, diferente da reclamação no call center) |

Correlações e cuidados:

- `alimentador` da ocorrência é **sempre** o alimentador cadastrado da
  `id_uc`, o que permite agregar por região (município/bairro) via cadastro.
- **Jul/2025** (evento climático, concentrado no `ALM-REC-008`) multiplica o
  DEC do mês por ~15. Decidir e documentar se o evento será expurgado, e
  mostrar os indicadores com e sem ele.
- O volume mensal acompanha o de atendimentos (correlação 0,98), puxado pelo
  pico de jul/2025. No nível de evento, porém, **não há vínculo**: só 0,6%
  dos atendimentos de falta de energia têm ocorrência na mesma UC nas 48 h
  anteriores. Ver [relacionamentos.md](relacionamentos.md#ocorrências--atendimentos).
- Causas acionáveis para manutenção preventiva: `VEGETACAO` e
  `FALHA DE EQUIPAMENTO`; `CLIMATICA` não é.
