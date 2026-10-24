# inspecoes.xlsx

Inspeções de campo para combate a perdas não técnicas (fraude/furto de
energia), com o resultado da vistoria, o tipo de irregularidade e a energia
recuperada.

- Formato: Excel, **3 abas** com o mesmo layout (`ago-set`, `out-nov`, `dez`)
- 1.389 linhas no total (511 + 495 + 383) · 7 colunas
- Grão: uma inspeção (cada UC foi inspecionada uma única vez)
- Chave primária: `id_inspecao` · Chave estrangeira: `id_uc` → UC
- Período: **ago/2025 a dez/2025**
- Todas as células estão gravadas como texto, inclusive números e datas

## Papel no domínio

- **Sistema de origem**: equipe de campo — "as inspeções de campo chegam em
  arquivos Excel preenchidos à mão", o que explica as grafias variadas.
- **Conceito do case**: *perdas não técnicas* — "energia entregue que não é
  faturada: furto ('gato'), fraudes no medidor ou erros de leitura e
  cadastro. É o que a equipe de perdas tenta recuperar com inspeções".
- **Papel no Grid 360**: é o **resultado real** (rótulo) que valida os sinais
  de suspeita da fila de inspeção e calibra a estimativa de energia a
  recuperar. O registro de novos resultados pelo portal (e o upload da
  planilha de campo, diferencial) segue este mesmo layout.

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_inspecao` | string | Identificador | `IN` + 7 dígitos (`IN0000000`–`IN0001388`), sequência completa distribuída entre as abas |
| `id_uc` | string | UC inspecionada | 1.389 UCs distintas, todas válidas |
| `data` | data | Data da inspeção | 2025-08-01 a 2025-12-31, em 4 formatos |
| `inspetor` | string | Código do inspetor | `INSP-001` a `INSP-040` (40 inspetores) |
| `resultado` | categoria | Conclusão | Irregularidade confirmada ou sem irregularidade (8 grafias) |
| `tipo_irregularidade` | categoria | Tipo de fraude | `DESVIO DIRETO`, `BY-PASS`, `MEDIDOR ADULTERADO`, `LIGACAO CLANDESTINA`, `LACRE VIOLADO`; vazio quando sem irregularidade |
| `kwh_recuperado` | decimal (kWh) | Energia recuperada/cobrada | `0` sem irregularidade; 89 a 15.609 kWh (mediana 1.073) quando confirmada |

### Normalização do resultado

| Valor no arquivo | Qtd. | Valor canônico |
|---|---:|---|
| `IRREGULARIDADE CONFIRMADA`, `Irregularidade Confirmada`, `irregularidade confirmada`, `CONFIRMADA` | 871 | `IRREGULARIDADE CONFIRMADA` |
| `SEM IRREGULARIDADE`, `Sem Irregularidade`, `sem irregularidade`, `NADA CONSTA` | 518 | `SEM IRREGULARIDADE` |

A normalização é confirmada pelos outros campos: todo resultado do primeiro
grupo tem `tipo_irregularidade` preenchido e `kwh_recuperado > 0`; todo
resultado do segundo grupo tem tipo vazio e `kwh_recuperado = 0`.

### Distribuições

- Taxa de acerto (irregularidade confirmada): **62,7%**.
- Os 5 tipos de irregularidade têm frequência e kWh recuperado semelhantes
  (mediana ~1.050–1.150 kWh).
- Inspeções concentradas em Recife (648) e Jaboatão (537), que também têm as
  maiores taxas de acerto (67% e 78%); nos demais municípios a taxa fica
  entre 0% e 13%.
- Por classe: Comercial 84% de acerto, Residencial 56%.

## Qualidade

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| Dados divididos em 3 abas | — | Ler todas as abas e concatenar |
| `data` fora do ISO: `DD/MM/AAAA` (43), `DD.MM.AAAA` (44), **`MM-DD-AAAA`** (46) — todas na aba `dez` | 133 | Parse pelo separador |
| Aba `dez` contém inspeções realizadas de ago a nov | 107 | Usar a coluna `data`, não o nome da aba, como período |
| `resultado` em 8 grafias | 164 fora do padrão | Mapeamento acima |
| `tipo_irregularidade` sem valor: célula vazia (311), `-` (77), `NULL` (68), `N/A` (62). Atenção: leitores como o pandas convertem `NULL`/`N/A` em nulo automaticamente, mas não `-` | 518 | Nulo |
| `inspetor` com espaços nas pontas (`' INSP-003'`, `'INSP-028  '`) | 83 | `trim` |
| `kwh_recuperado` com vírgula decimal (`1313,70`) | 125 | Trocar vírgula por ponto |

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Fila de inspeção (Perdas) | Valida os sinais: com queda de consumo > 10% (sem GD), o acerto seria de 92%, contra os 62,7% atuais ("pouco mais da metade") |
| Energia a recuperar | `kwh_recuperado` ≈ 6 × a queda mensal de consumo (correlação 0,92), o que dá uma fórmula para estimar o potencial de cada UC suspeita |
| Diagnóstico da receita | As 871 UCs com fraude confirmada perderam 51% do volume (−2,6 GWh, ≈ −R$ 1,8 mi), concentradas em 4 bairros (Iputinga, Jardim Jordão, Prazeres, Macaxeira) |
| Registro de resultados / upload da planilha | O layout destas abas é o formato de entrada esperado; a normalização de `resultado`, datas e decimais deve ser reaproveitada |
| Agente de IA | "Gato", "fraude", "furto" → inspeções com irregularidade confirmada |

Correlações (ver [relacionamentos.md](relacionamentos.md#inspeções--leituras-sinal-de-fraude)):

- O consumo das fraudadoras cai em mai–jun/2025, ~4–5 meses antes da
  inspeção, e se recupera só parcialmente depois (~50% da base).
- Taxa de acerto maior em Comercial (84%) e em Jaboatão/Recife.
- As fraudadoras não diferem na inadimplência nem no número de atendimentos.
