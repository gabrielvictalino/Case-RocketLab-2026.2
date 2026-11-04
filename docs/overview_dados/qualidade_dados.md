# Qualidade dos dados e regras de tratamento

Catálogo consolidado dos problemas encontrados nos arquivos brutos, agrupados
por tipo, com a regra de tratamento sugerida para a camada silver. Os
detalhes e contagens por arquivo estão nos documentos de cada fonte.

## Leitura dos arquivos

- **Ler tudo como texto** (`dtype=str`) na bronze. Vários campos numéricos e
  de data contêm texto (`R$ 225,53`, `23 min`, `N/A`), e a inferência
  automática de tipos falharia ou descartaria valores.
- **Desativar a conversão automática de nulos** ao perfilar
  (`keep_default_na=False` no pandas). Por padrão, `NULL`, `null`, `N/A` e
  `-1.#IND` viram nulo silenciosamente, mas `-`, `-1` e `9999-12-31` não —
  tratar todos explicitamente evita regras inconsistentes.
- `faturas.csv` usa `;` como separador; os demais CSVs usam `,`.
- `inspecoes.xlsx` tem os dados distribuídos em 3 abas, todas com o mesmo
  cabeçalho.
- `atendimentos.json` é um único array de 154 MB com listas aninhadas.

## Registros a descartar

| Tipo | Onde | Como identificar | Qtd. |
|---|---|---|---:|
| Cabeçalho repetido no meio do arquivo | unidades_consumidoras, faturas | Valor da chave igual ao nome da coluna | 1 + 2 |
| Registros de teste | unidades_consumidoras | `id_uc` começando com `TESTE` | 200 |
| Duplicatas exatas | unidades_consumidoras, medidores, leituras | Linha inteira repetida | 900 / 513 / 21.523 |
| Duplicatas com variação de grafia | unidades_consumidoras | Mesmo `id_uc`, nome em caixa diferente ou CPF formatado | 360 |
| Faturas órfãs | faturas | `id_fatura` com `FTX`; `id_uc` com 9 caracteres (`UC9…`) | 32.285 |
| Leituras espúrias | leituras | `id_leitura` com `LTX`; `id_medidor` com 9 caracteres (`MD9…`) | 8.609 |

Sugestão: em vez de apagar, enviar registros rejeitados para uma tabela de
quarentena com o motivo, para auditoria.

Regex de validação das chaves:

| Chave | Padrão válido |
|---|---|
| `id_uc` | `^UC\d{6}$` |
| `id_medidor` | `^MD\d{6}$` |
| `id_leitura` | `^LT\d{9}$` |
| `id_fatura` | `^FT\d{9}$` |
| `id_ocorrencia` | `^OC\d{8}$` |
| `protocolo` | `^AT\d{9}$` |
| `id_inspecao` | `^IN\d{7}$` |
| `alimentador` | `^ALM-[A-Z]{3}-\d{3}$` |

## Datas

Quatro formatos convivem nos mesmos campos. O **separador identifica o
formato sem ambiguidade** — verificado pelo dia (> 12) em cada posição e pela
coerência com `mes_referencia`:

| Exemplo | Separador | Formato |
|---|---|---|
| `2025-04-26` | `-` com ano primeiro | `AAAA-MM-DD` (ISO) |
| `26/04/2025` | `/` | `DD/MM/AAAA` |
| `26.04.2025` | `.` | `DD.MM.AAAA` |
| `04-26-2025` | `-` com ano no fim | **`MM-DD-AAAA`** (americano) |

Atenção ao último: interpretá-lo como `DD-MM-AAAA` troca dia e mês em silêncio
sempre que o dia for ≤ 12.

| Campo | Fora do ISO |
|---|---:|
| `leituras.data_leitura` | ~259 mil (12%) |
| `faturas.data_emissao` | 183.361 (8%) |
| `medidores.data_instalacao` | 3.728 (7%) |
| `inspecoes.data` | 133 (10%) |

Data-hora: protocolos e ocorrências usam `AAAA-MM-DD HH:MM:SS`; o histórico de
atendimentos usa `AAAA-MM-DDTHH:MM:SS`.

## Valores sentinela e marcadores de nulo

| Valor | Significado | Onde |
|---|---|---|
| `9999-12-31` | "sem data fim" / não pago | `medidores.data_retirada`, `faturas.data_pagamento`, também em `unidades_consumidoras.cep` |
| `1900-01-01` … `1948-01-01` | data desconhecida | `unidades_consumidoras.data_ligacao` (92) |
| `-1` | valor desconhecido | `leituras.leitura_anterior`, `unidades_consumidoras.cep` |
| `NULL`, `null`, `N/A`, `-`, espaços | ausente | `cep`, `causa`, `leitura_anterior`, `tipo_irregularidade` |

Regra: converter todos para nulo na silver.

## Categorias inconsistentes

| Campo | Variações | Canônico |
|---|---|---|
| `unidades_consumidoras.uf` | `PE`, `pe`, `pernambuco`, `Pernambuco`, `P.E.` | `PE` |
| `unidades_consumidoras.classe` | caixa variada; `Poder Público` / `Poder Publico` | `RESIDENCIAL`, `COMERCIAL`, `INDUSTRIAL`, `RURAL`, `PODER PUBLICO` |
| `medidores.tipo` | `Eletronico`, `eletrônico`, `ELETRO-MECANICO`, `eletromecânico`, `smart meter`, `Smart`… | `ELETRONICO`, `ELETROMECANICO`, `SMART` |
| `inspecoes.resultado` | 8 grafias, incluindo `CONFIRMADA` e `NADA CONSTA` | `IRREGULARIDADE CONFIRMADA`, `SEM IRREGULARIDADE` |

Regra geral: `trim` → `upper` → remover acentos → mapa de sinônimos.

## Números em formato textual

| Campo | Exemplo | Regra |
|---|---|---|
| `faturas.valor_total` | `R$ 1.234,56` | Remover `R$` e `.`; trocar `,` por `.` |
| `geracao_distribuida.potencia_kwp` | `5,53` | Trocar `,` por `.` |
| `inspecoes.kwh_recuperado` | `1313,70` | Trocar `,` por `.` |
| `ocorrencias_rede.duracao_min` | `23 min` | Extrair dígitos (ou recalcular pelas datas) |
| `unidades_consumidoras.cpf_cnpj` | `439.810.983-82` | Manter só dígitos |
| `leituras.consumo_kwh` | `-101.0` | Converter para inteiro (e ver sinal abaixo) |

## Encoding

`unidades_consumidoras.bairro` tem 356 linhas (59 nomes) com texto UTF-8
que foi lido como Latin-1 e regravado (*mojibake*): `Jardim JordÃ£o` em vez
de `Jardim Jordão`. Sem correção, o mesmo bairro aparece com duas grafias e
os recortes por bairro — pedidos explicitamente pelo Diretor Comercial —
ficam divididos. Regra: aplicar `encode('latin-1').decode('utf-8')` só aos
valores que casam com `[ÃÂ][\u0080-\u00bf]`; `Rio Âmbar` é legítimo. Após a
correção, restam 272 bairros.

## Espaços extras

`unidades_consumidoras.logradouro`, `medidores.modelo` e
`inspecoes.inspetor` têm espaços no início/fim. Aplicar `trim` em todas as
colunas de texto.

## Inconsistências semânticas

| Problema | Regra sugerida |
|---|---|
| Consumo negativo na troca de medidor (anterior e atual de medidores diferentes) | Marcar `flag_troca_medidor`; excluir de médias |
| Consumo negativo com sinal invertido | Usar o valor absoluto quando `atual − anterior` = `−consumo` |
| `consumo_kwh` difere de `atual − anterior` em ±1 | Aceitar (arredondamento) |
| `potencia_kwp` > 75 com injeção típica de ~5 kWp | Dividir por 1.000 (provável registro em Wp) |
| Aba `dez` das inspeções contém inspeções de outros meses | Usar a coluna `data` |
| `acao` do histórico de atendimentos fora de ordem lógica | Ordenar por `sequencia`; não inferir etapas pela ação |
| `medidores.data_ultima_manutencao` 100% vazia | Descartar a coluna |
| `data_ligacao` implausível | Substituir pela `data_instalacao` do primeiro medidor |

## Validações recomendadas para a silver (testes de dados)

- Unicidade: `id_uc` em UCs; `id_medidor`; `id_leitura`; `id_fatura`;
  `(id_uc, mes_referencia)` em leituras e em faturas.
- Integridade referencial: todas as FKs da tabela em
  [relacionamentos.md](relacionamentos.md#chaves-de-junção).
- `valor_total = valor_energia + tributos` (tolerância de R$ 0,01).
- `data_vencimento = data_emissao + 12 dias`.
- `status = 'PAGA'` ⇔ `data_pagamento` não nula.
- `duracao_min = data_encerramento − data_abertura`.
- Exatamente 1 medidor `ATIVO` por UC.
- `classe` determina `subgrupo_tarifario` (Residencial→B1, Rural→B2,
  Comercial/Poder Público→B3, Industrial→A4).
- `kwh_recuperado > 0` ⇔ resultado `IRREGULARIDADE CONFIRMADA`.
