# atendimentos.json

Protocolos de atendimento ao cliente (central, app, site, WhatsApp,
presencial), com assunto, datas, nota de satisfação e o histórico de
tratativas aninhado.

- Formato: JSON, um array de objetos (154 MB) · 318.871 protocolos
- Grão: um protocolo de atendimento
- Chave primária: `protocolo` · Chave estrangeira: `id_uc` → UC
- Estrutura **aninhada**: cada protocolo tem uma lista `historico` com
  1 a 3 eventos (636.857 eventos no total)

## Papel no domínio

- **Sistema de origem**: call center, exportado em JSON ("o call center
  manda JSONs").
- **Conceito do case**: chamados do cliente, com histórico de tratativas e
  nota de satisfação.
- **Papel no Grid 360**: "os chamados que ele já abriu" na visão 360,
  volume e satisfação nos indicadores, e a voz do cliente (ex.: reclamações
  de conta alta).

Exemplo de registro:

```json
{
  "protocolo": "AT000000001",
  "id_uc": "UC100661",
  "canal": "SITE",
  "assunto": "FALTA DE ENERGIA",
  "subassunto": "INTERRUPCAO TOTAL",
  "data_abertura": "2022-07-07 23:25:00",
  "data_fechamento": "2022-07-17 10:25:00",
  "nota_satisfacao": 4.1,
  "historico": [
    {"sequencia": 1, "data": "2022-07-12T16:25:00", "acao": "RETORNO AO CLIENTE", "canal": "SITE"},
    {"sequencia": 2, "data": "2022-07-17T10:25:00", "acao": "DESPACHO", "canal": "SITE"}
  ]
}
```

## Campos do protocolo

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `protocolo` | string | Identificador | `AT` + 9 dígitos, sem repetição |
| `id_uc` | string | UC do cliente | 44.940 UCs, todas válidas; 1 a 20 protocolos por UC (média 7,1) |
| `canal` | categoria | Canal de entrada | `TELEFONE`, `APP`, `WHATSAPP`, `SITE`, `PRESENCIAL` (~20% cada) |
| `assunto` | categoria | Assunto principal | `FALTA DE ENERGIA` (32%); `FATURA`, `DANO ELETRICO`, `LIGACAO NOVA`, `GERACAO DISTRIBUIDA`, `RELIGACAO` (~14% cada) |
| `subassunto` | categoria | Detalhamento | Depende do assunto (tabela abaixo) |
| `data_abertura` | data-hora | Abertura | `AAAA-MM-DD HH:MM:SS`, jul/2022 a jun/2026 |
| `data_fechamento` | data-hora | Encerramento | Sempre após a abertura: 1 h a 30 dias (mediana ~5 dias) |
| `nota_satisfacao` | decimal | Nota do cliente | 1,3 a 5,0 (uma casa); média 4,04; `null` em 9.566 (3%) |
| `historico` | lista de objetos | Tratativas do protocolo | 1, 2 ou 3 eventos (~1/3 cada) |

## Campos de `historico[]`

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `sequencia` | inteiro | Ordem do evento | 1 a 3, em ordem cronológica |
| `data` | data-hora | Momento do evento | **`AAAA-MM-DDTHH:MM:SS`** (com `T`, diferente do protocolo); o último evento sempre coincide com `data_fechamento` |
| `acao` | categoria | Ação executada | `ABERTURA`, `ANALISE`, `DESPACHO`, `RETORNO AO CLIENTE`, `ENCERRAMENTO` (~20% cada) |
| `canal` | categoria | Canal do evento | Sempre igual ao `canal` do protocolo (redundante) |

## Hierarquia assunto → subassunto

| Assunto | Subassuntos |
|---|---|
| `FALTA DE ENERGIA` | `INTERRUPCAO TOTAL`, `INTERRUPCAO PARCIAL`, `OSCILACAO` |
| `FATURA` | `VALOR ALTO`, `SEGUNDA VIA`, `CONTESTACAO`, `PARCELAMENTO` |
| `DANO ELETRICO` | `RESSARCIMENTO`, `VISTORIA` |
| `LIGACAO NOVA` | `SOLICITACAO`, `PRAZO`, `VISTORIA` |
| `GERACAO DISTRIBUIDA` | `HOMOLOGACAO`, `CREDITOS`, `VISTORIA` |
| `RELIGACAO` | `URGENCIA`, `APOS PAGAMENTO` |

`VISTORIA` aparece em três assuntos: a chave do subassunto é o par
`(assunto, subassunto)`.

## Qualidade

O arquivo é estruturalmente limpo: todos os objetos têm as mesmas chaves,
sem duplicatas nem datas inválidas. Pontos de atenção:

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| `nota_satisfacao` nula (cliente não avaliou) | 9.566 | Manter nulo; não tratar como zero |
| `acao` não segue o fluxo esperado: só 20% dos protocolos começam com `ABERTURA`, e `ENCERRAMENTO` pode ser o 1º evento (a ação é aleatória em cada posição) | ~255 mil protocolos | Usar `sequencia`/`data` para ordenar; não confiar em `acao` para definir etapas |
| Formatos de data-hora diferentes entre protocolo (espaço) e histórico (`T`) | todos | Padronizar no parse |
| Arquivo único de 154 MB em array JSON | — | Ler em streaming (ex.: `ijson`) se a memória for limitada |

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Visão 360 (Atendimento) | Lista de protocolos da UC com assunto, nota e linha do tempo do `historico` |
| "Conta alta" | Reclamações `FATURA / VALOR ALTO` cruzadas com leituras e faturas: só ~20% tiveram consumo mais de 10% acima do ano anterior — a tela deve mostrar consumo, bandeira e tarifa lado a lado |
| Indicadores da diretoria | Volume de chamados e satisfação; a nota cai para 3,1 quando o atendimento passa de 14 dias |
| Agente de IA | Perguntas sobre "atendimento", "reclamações", "falta de luz" (reclamação, diferente do evento de rede) |

Correlações e cuidados:

- Na camada silver, separar em duas tabelas: `atendimentos` (1 linha por
  protocolo) e `atendimentos_historico` (1 linha por evento, FK `protocolo`).
- A nota praticamente não varia por canal ou assunto (≈ 4,04 em todos): o
  tempo de resolução é o único fator com efeito visível (correlação −0,27).
- O volume é estável (~6.400/mês), com **pico em jul/2025 (18.061, ×3)**, no
  mesmo mês do evento climático em ocorrencias_rede. Todos os assuntos
  triplicaram, não só falta de energia. A ligação com ocorrências só existe
  no agregado mensal.
- O assunto `GERACAO DISTRIBUIDA` não tem relação com a UC ter GD (ver
  [geracao_distribuida.md](geracao_distribuida.md)).
