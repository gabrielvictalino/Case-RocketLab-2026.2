# Contrato local provisório — 0.1.0-provisional

**Não aprovado pelo time de dados. Somente dados sintéticos.** As 12 tabelas de
`tabelas/*.yaml` derivam da seção 3 do system design, com grão, chave, tipos,
unidades, nulabilidade, referências e totais de controle. Os arquivos YAML usam
a sintaxe JSON, que é um subconjunto válido de YAML.

O importador não estima consumo, calcula scores nem determina regras oficiais
de receita ou DEC/FEC. Valida tipos e estrutura recebidos e a consistência entre
detalhe mensal e agregado comercial. Componentes de preço e bandeira desta versão
são uma convenção estritamente sintética para testar a reconciliação, não uma
implementação da decomposição oficial da receita.

## Convenções de intercâmbio

- UTF-8, CSV com vírgula, cabeçalho e ordem de colunas exatamente como o contrato.
- Nulo é campo vazio, somente em colunas explicitamente anuláveis.
- Decimal com ponto, precisão e escala declaradas, sem notação monetária.
- Booleanos `true`/`false`; JSON apenas para lista de motivos da fila.
- Competência é data ISO do primeiro dia do mês. O manifesto usa `AAAA-MM`.
- Datas de inspeção são datas locais; timestamps de rede e atendimento são ISO
  sem fuso, conforme a Silver de ocorrências (TIMESTAMP_NTZ). Eventos criados
  pelo portal usam `timestamptz`.
- `manifest.schema.json` exige todas as tabelas, contagens, SHA-256 e totais de
  controle. A versão precisa coincidir com `VERSION`. `synthetic` precisa ser true
  nesta versão, verificado também pelo importador.
- Sem nome, CPF ou endereço reais: titular e endereço são inventados e o documento
  já vem mascarado. A view de IA `ucs` omite esses três campos.
- Inspeções históricas usam `IN` + 7 dígitos; novas inspeções usam `PORTAL-<UUID>`.
  A view unificada inclui `origem`. Tipos de irregularidade ainda são texto livre:
  a auditoria e o overview apresentam listas divergentes; não fixamos um enum falso.

## Amostra e reprodução

```bash
uv run python contracts/samples/gerar.py
uv run pytest importador/tests/test_contracts.py -q
```

São 300 UCs, 3 municípios, 6 bairros, 5 classes e 6 alimentadores, cobrindo
jul/2022–jun/2026. Há UC nova sem ano anterior, GD conectada em jan/2025,
irregularidade confirmada, consumo original negativo na troca de medidor,
leitura estimada, faturas em aberto, nota nula, inspeções anteriores de ambos
os resultados, candidatos para reinspeção e evento atípico em jul/2025.
O alimentador com uma UC tem DEC maior que os demais nos meses comuns,
mas CHI menor que o do evento atípico.

Todos os números vêm de constantes/fórmulas do gerador, sem sorteio e sem dados
externos. O agregado de receita é gerado a partir do detalhe com `Decimal`.
No gerador, consumo analítico da troca é um valor inventado identificado por
`SINTETICO_TROCA`; não adota média ou mediana. A flag de irregularidade no cadastro
é o retrato atual; os grupos mensais são temporais na amostra. O denominador de
continuidade usa o cadastro sintético atual, sujeito a substituição no contrato
real. Não há tratamento oficial de sobreposição nem limiar oficial de score.

Para trocar pelo contrato real, é necessário aprovar as pendências em
[`docs/backend-pendencias.md`](../docs/backend-pendencias.md), versionar os novos
contratos, adaptar o produtor Gold e atualizar importador, amostras e testes no
mesmo ciclo. Não renomear esta versão como aprovada sem essa revisão.
