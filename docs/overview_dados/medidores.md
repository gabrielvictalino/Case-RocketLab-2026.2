# medidores.csv

Histórico de medidores de energia instalados em cada UC, incluindo os já
retirados. Permite saber qual equipamento gerou cada leitura e acompanhar a
modernização do parque de medição.

- Separador: `,` · 51.812 linhas · 8 colunas
- Grão: um medidor (equipamento) em uma UC
- Chave primária: `id_medidor` · Chave estrangeira: `id_uc` → UC

## Papel no domínio

- **Sistema de origem**: medição (cadastro do parque de medidores).
- **Conceito do case**: a UC é definida como o ponto "que tem um medidor".
  O medidor é o equipamento que gera as leituras e o alvo de parte das
  fraudes (medidor adulterado, by-pass, lacre violado).
- **Papel no Grid 360**: informa qual medidor está instalado (visão 360) e
  explica comportamentos das leituras: leituras estimadas, consumos negativos
  na troca e modernização do parque.

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_medidor` | string | Identificador do medidor | `MD` + 6 dígitos (`MD500000`…) |
| `id_uc` | string | UC onde está/esteve instalado | 45.000 UCs, todas existentes no cadastro |
| `modelo` | categoria | Modelo do equipamento | 9 modelos: `EL-2200`, `EL-3000`, `NX-700`, `EM-1200`, `EM-1400`, `CG-500`, `IQ-900`, `SM-4100`, `SM-4500` |
| `tipo` | categoria | Tecnologia | `ELETRONICO`, `ELETROMECANICO`, `SMART` |
| `data_instalacao` | data | Instalação na UC | 1997 a mar/2026 |
| `data_retirada` | data | Retirada da UC | set/2025 a mar/2026; nulo ou `9999-12-31` se ativo |
| `data_ultima_manutencao` | data | Última manutenção | **100% vazio** |
| `status` | categoria | Situação | `ATIVO` (45.445), `RETIRADO` (6.367) |

### Relações internas

- **Modelo → tipo** (prefixo indica a tecnologia): `EM-*` e `CG-*` são
  eletromecânicos; `EL-*` e `NX-*` eletrônicos; `SM-*` e `IQ-*` smart.
- Após deduplicar, **toda UC tem exatamente um medidor `ATIVO`**. UCs com
  2 a 4 registros representam trocas: o antigo fica `RETIRADO` e a sua
  `data_retirada` coincide com a `data_instalacao` do substituto.
- `status = RETIRADO` ⇔ `data_retirada` preenchida com data real.

### Troca em massa (smart meters)

Todas as 6.367 retiradas ocorreram entre **set/2025 e mar/2026**, e no
mesmo período foram instalados ~6.600 medidores, ~90% deles `SMART`. Antes
disso, quase não há instalações (44–100 por ano entre 2022 e 2024). É um
programa de modernização, útil para cruzar com a queda de leituras
estimadas em 2026 (ver [leituras.md](leituras.md)).

## Qualidade

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| Duplicatas exatas | 513 | `DISTINCT` |
| `tipo` com 10 grafias (`Eletronico`, `eletrônico`, `ELETRO-MECANICO`, `smart meter`, `Smart`…) | 5.354 | Mapear para os 3 valores canônicos (ou derivar do `modelo`) |
| `modelo` com espaços nas pontas (`'  EL-3000 '`) | 3.109 | `trim` |
| `data_instalacao` fora do ISO: `DD/MM/AAAA` (1.249), `DD.MM.AAAA` (1.216), **`MM-DD-AAAA`** (1.263) | 3.728 | Parse pelo separador (ver [qualidade_dados.md](qualidade_dados.md#datas)) |
| `data_retirada = 9999-12-31` em medidor ativo (sentinela de "sem data fim") | 13.649 | Nulo |
| `data_ultima_manutencao` sempre vazia | 51.812 | Descartar a coluna ou manter como nula |

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Visão 360 (Atendimento) | "O medidor instalado": modelo, tipo (smart ou não), data de instalação e histórico de trocas |
| Diagnóstico da receita | Identifica os ~6.250 meses de **troca de medidor** com consumo inválido; tratá-los muda a variação de volume de −5,1% para −4,0% |
| Fila de inspeção | **Tipo do medidor como sinal**: nos 4 bairros com fraude, inspeções em UCs com medidor `ELETROMECANICO` acertaram 92%, contra 12,5% com `ELETRONICO`; fora desses bairros o tipo não separa (≈ 5–9%). Use o tipo combinado com a localização, não isoladamente |
| Integridade referencial | Destino da FK `leituras.id_medidor`; o medidor de cada leitura pertence sempre à mesma UC |

Correlações:

- Nenhuma leitura é posterior à retirada do seu medidor: o histórico é
  temporalmente consistente.
- A troca em massa por `SMART` (set/2025–mar/2026) coincide com a queda das
  leituras estimadas de ~19% para 14% em 2026.
