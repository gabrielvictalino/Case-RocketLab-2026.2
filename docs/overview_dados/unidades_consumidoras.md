# unidades_consumidoras.csv

Cadastro das unidades consumidoras (UCs): o ponto de entrega de energia,
com titular, endereço, classificação tarifária e alimentador da rede.
É a **tabela-dimensão central**: todas as demais fontes referenciam `id_uc`.

- Separador: `,` · Codificação: UTF-8 · 46.461 linhas · 16 colunas
- Grão: uma UC (após limpeza)
- Chave primária: `id_uc`

## Papel no domínio

- **Sistema de origem**: cadastro comercial.
- **Conceito do case**: a *unidade consumidora* é "o ponto que recebe energia
  e tem um medidor: uma casa, uma loja, uma fábrica", e é a entidade central
  do case. A *classe de consumo* define o *subgrupo tarifário* (B1
  residencial, B2 rural, B3 comercial e poder público, A4 industrial em média
  tensão), e é o subgrupo que define a tarifa. O *alimentador* é o circuito de
  média tensão que abastece um conjunto de ruas: quando falha, todas as UCs
  ligadas a ele ficam sem luz.
- **Papel no Grid 360**: é a "fonte única de verdade" do cliente. O número da
  UC impresso na conta é a chave de busca do atendente, e os atributos
  classe, município, bairro e alimentador são os recortes de todas as
  análises.
- O case observa que "um mesmo cliente pode ter várias UCs". Nesta base, após
  limpar o documento, cada CPF/CNPJ aparece em uma única UC.

## Campos

| Campo | Tipo lógico | Descrição | Domínio / observações |
|---|---|---|---|
| `id_uc` | string | Identificador da UC | `UC` + 6 dígitos (`UC100000`–`UC144999`). 45.000 UCs reais |
| `cpf_cnpj` | string | Documento do titular | CPF (11 dígitos) ou CNPJ (14 dígitos), às vezes formatado |
| `nome_titular` | string | Nome da pessoa ou razão social | 27.945 nomes distintos |
| `logradouro` | string | Rua/avenida | 1.557 distintos; espaços extras nas pontas |
| `numero` | inteiro | Número do imóvel | 1–2399 |
| `bairro` | string | Bairro | 272 bairros reais (331 grafias distintas no arquivo, por causa do encoding) |
| `municipio` | string | Município | 14 municípios da RMR (ver abaixo) |
| `uf` | string | Estado | Sempre Pernambuco, em 5 grafias |
| `cep` | string(8) | CEP sem máscara | Faixa 50000-000 a 56999-999; ~3% inválidos |
| `classe` | categoria | Classe de consumo | Residencial, Comercial, Industrial, Rural, Poder Público |
| `subgrupo_tarifario` | categoria | Subgrupo ANEEL | `B1`, `B2`, `B3`, `A4` (determinado pela classe) |
| `alimentador` | string | Circuito da rede que atende a UC | `ALM-<MUN>-<NNN>`, 122 alimentadores |
| `data_ligacao` | data | Data de ligação da UC | Ligações reais de 1997 a mar/2026; 92 datas implausíveis (1900–1948) |
| `status` | categoria | Situação da UC | Apenas `ATIVA` |
| `latitude` | decimal | Latitude (2 casas) | −8,46 a −7,70 |
| `longitude` | decimal | Longitude (2 casas) | −35,14 a −34,78 |

### Distribuições principais

- **Classe** (normalizada): Residencial 39.596 · Comercial 5.065 ·
  Industrial 900 · Rural 671 · Poder Público 228 (contagens antes de deduplicar).
- **Classe → subgrupo** é determinística: Residencial→`B1`, Rural→`B2`,
  Comercial e Poder Público→`B3`, Industrial→`A4` (média tensão).
- **Municípios**: Recife (40%), Jaboatão dos Guararapes (17%), Olinda,
  Paulista, Cabo de Santo Agostinho, Camaragibe, São Lourenço da Mata,
  Igarassu, Ipojuca, Abreu e Lima, Moreno, Itapissuma, Ilha de Itamaracá,
  Araçoiaba.
- **Alimentador ↔ município**: o trecho do meio do código identifica o
  município (`REC` Recife, `JAB` Jaboatão, `OLI` Olinda, `PAU` Paulista,
  `CAB` Cabo, `CAM` Camaragibe, `SAO` São Lourenço, `IGA` Igarassu,
  `IPO` Ipojuca, `ABR` Abreu e Lima, `MOR` Moreno, `ITA` Itapissuma,
  `ILH` Itamaracá, `ARA` Araçoiaba). Recife tem 48 alimentadores, Jaboatão 21.
- Coordenadas com apenas 2 casas decimais (~1 km de precisão): servem para
  mapas por região, não para geolocalização do imóvel.

## Qualidade

| Problema | Ocorrências | Tratamento sugerido |
|---|---:|---|
| Cabeçalho repetido no meio do arquivo (linha 27.535) | 1 | Descartar linha onde `id_uc = 'id_uc'` |
| UCs de teste `TESTE0000`–`TESTE0199` (titular `a`, `XXXX`, `TESTE`; CPF `00000000000`) | 200 | Descartar `id_uc` fora do padrão `^UC\d{6}$` |
| Duplicatas exatas | 900 | `DISTINCT` |
| Mesma UC com nome em caixa alta e/ou CPF formatado | 360 | Normalizar e deduplicar por `id_uc` |
| `uf` em 5 grafias (`PE`, `pe`, `pernambuco`, `Pernambuco`, `P.E.`) | 6.990 fora de `PE` | Mapear tudo para `PE` |
| `classe` com variação de caixa e acento (`RESIDENCIAL`, `residencial`, `Poder Público`) | 2.863 | `upper` + remover acento |
| `cpf_cnpj` formatado (`439.810.983-82`, `80.061.230/0001-08`) | 4.599 | Manter só dígitos; tipo pelo tamanho (11 = CPF, 14 = CNPJ) |
| `cep` inválido: `N/A`, `NULL`, `null`, `-`, `-1`, `9999-12-31`, espaços, vazio | 1.383 | Converter para nulo |
| `logradouro` com espaço no início/fim | 2.797 | `trim` |
| `bairro` com **encoding corrompido** (UTF-8 lido como Latin-1: `Jardim JordÃ£o`, `Vila Torres GalvÃ£o`) | 356 linhas, 59 nomes | Recodificar `latin-1 → utf-8` apenas nos valores com `Ã`/`Â` seguido de caractere de continuação; `Rio Âmbar` é grafia legítima e não deve ser alterada |
| `data_ligacao` implausível: sempre `AAAA-01-01` entre 1900 e 1948 (a base real começa em 1997) | 92 | Nulo |

Observação: depois de remover a máscara, o tamanho do documento não basta
para distinguir CPF formatado (14 caracteres) de CNPJ sem máscara (14
dígitos); faça a limpeza **antes** de classificar.

## Uso no case

Detalhes e números em [perguntas_negocio.md](perguntas_negocio.md).

| Necessidade (persona / requisito) | Como esta fonte é usada |
|---|---|
| Diagnóstico da receita (Diretor Comercial) | Recortes por **município, bairro e classe** para o drill-down do efeito-volume. A queda de volume residencial concentra-se em Iputinga, Macaxeira, Jardim Jordão e Prazeres |
| Visão 360 (Atendimento) | Bloco "quem é o cliente": nome, classe/subgrupo, endereço, alimentador; busca por `id_uc` |
| DEC/FEC (Operação) | **Denominador** dos indicadores: número de UCs por `alimentador` (de 20 a 2.285 UCs) |
| Fila de inspeção (Perdas) | Localização e classe como fatores de priorização: 96% das fraudes estão em 4 bairros; Comercial tem 84% de acerto |
| Agente de IA | Dimensão de filtros em linguagem natural ("em Olinda", "residencial", "no bairro X") |
| Integridade referencial (Eng. de Dados) | Tabela-mãe de todas as FKs `id_uc`; define o universo de 45.000 UCs válidas |

Cuidados:

- O bairro só serve de recorte depois da correção de encoding: sem ela, o
  mesmo bairro aparece com duas grafias (`Jardim Jordão` / `Jardim JordÃ£o`)
  e o volume fica dividido.
- `data_ligacao` é igual à instalação do primeiro medidor em 99,8% das UCs
  (ver [medidores.md](medidores.md)); essa data pode substituir as 92 datas
  de ligação implausíveis.
- Contém dados pessoais (nome, CPF, endereço): mascarar na visão 360 e
  impedir que o agente de IA os exponha (LGPD; requisito de segurança da IA).
