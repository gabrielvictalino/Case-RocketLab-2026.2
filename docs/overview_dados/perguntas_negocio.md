# Dados × requisitos e perguntas de negócio do case

Como cada fonte de dados atende às necessidades descritas no
Case Final — V-Energy Grid 360:
as perguntas das lideranças, as user stories da seção 5.2 e a pergunta que
originou o projeto — **por que o volume faturado caiu e a receita subiu tão
pouco?**

> Os números abaixo vêm da análise exploratória dos arquivos brutos, com as
> regras de limpeza de [qualidade_dados.md](qualidade_dados.md) aplicadas em
> pandas. Servem como **evidência e hipótese**: devem ser recalculados nas
> tabelas Gold do pipeline antes de entrar no diagnóstico final ou no portal.

Períodos usados nas comparações:

- **P0** = jul/2022–jun/2023: primeiro ano da base (referência do Diretor Comercial).
- **P1** = jul/2025–jun/2026: últimos 12 meses.
- **Ano anterior** = jul/2024–jun/2025, para comparações ano contra ano.

## 1. Fontes, sistemas de origem e papéis no domínio

O case descreve sistemas isolados, cada um com "a sua versão do cliente". A
tabela liga cada arquivo ao sistema de origem, ao conceito do glossário
(seção 3.2 do case) e a quem usa a informação.

| Arquivo | Sistema de origem | Conceito do domínio | Quem usa | Papel no Grid 360 |
|---|---|---|---|---|
| [unidades_consumidoras](unidades_consumidoras.md) | Cadastro comercial | **Unidade consumidora (UC)**, **classe de consumo / subgrupo**, **alimentador** | Todos | Dimensão central: liga todas as fontes e define os recortes (classe, município, bairro, alimentador) |
| [leituras](leituras.md) | Medição | Consumo por **competência** (kWh) | Comercial, Atendimento, Perdas | **Quantidade** de energia: efeito-volume, histórico de consumo, sinal de fraude |
| [faturas](faturas.md) | Faturamento | **Competência**, **bandeira tarifária**, receita | Comercial, Atendimento | **Receita e preço**: efeito-preço, faturas em aberto |
| [medidores](medidores.md) | Medição (parque) | Medidor da UC | Atendimento, Perdas | Equipamento instalado; explica leituras estimadas e consumos negativos na troca |
| [geracao_distribuida](geracao_distribuida.md) | Cadastro de GD | **Geração distribuída** (energia abatida do consumo faturado) | Comercial, Atendimento, Perdas | Principal explicação da queda de volume; falso positivo a excluir da fila de perdas |
| [ocorrencias_rede](ocorrencias_rede.md) | Sistema de operação da rede | Interrupção; base de **DEC e FEC** | Operação, Atendimento | Continuidade por alimentador; "a rua dele teve falta de luz?" |
| [atendimentos](atendimentos.md) | Call center (exportação JSON) | Chamado, satisfação | Atendimento | Histórico de chamados do cliente na visão 360 |
| [inspecoes](inspecoes.md) | Equipe de campo (Excel preenchido à mão) | **Perdas não técnicas** | Perdas | Rótulo (resultado real) para calibrar a fila de inspeção e estimar energia recuperável |

## 2. Diagnóstico da receita — Henrique Duarte, Diretor Comercial

> "Comparando os últimos 12 meses com o primeiro ano da nossa base, o volume
> de energia faturada caiu quase 4% e a receita subiu só 8%. [...] Quero saber
> quanto da variação foi preço e quanto foi quantidade de energia. Se foi
> volume, quero saber onde e por quê."

Requisitos atendidos: diagnóstico da receita (5.2.4); user story do diretor
comercial (efeito-preço × efeito-volume por município, bairro e classe).

### Fontes e junção

`faturas` (receita = `valor_total`, bandeira) ⋈ `leituras` (volume =
`consumo_kwh`) por `(id_uc, mes_referencia)` ⋈ `unidades_consumidoras`
(classe, município, bairro) ⋈ `geracao_distribuida` e `inspecoes` (para
explicar o volume).

### Os dados reproduzem a fala da diretoria

| Métrica | P0 | P1 | Variação |
|---|---:|---:|---:|
| Receita faturada (`valor_total`) | R$ 157,1 mi | R$ 169,7 mi | **+8,0%** |
| Volume faturado (kWh) | 227,1 GWh | 217,9 GWh | **−4,0%** |
| UCs faturadas | 44.741 | 45.000 | +0,6% |
| Tarifa base residencial (sem bandeira e sem tributos) | R$ 0,5305/kWh (jul/2022) | R$ 0,5863/kWh (jun/2026) | **+10,5%** (exatamente o reajuste citado no case) |

O volume só fecha em −4,0% quando os ~6.250 meses de **troca de medidor**,
que têm consumo inválido, são estimados pela mediana da própria UC. Sem esse
tratamento, a queda aparece como −5,1%. É uma decisão de limpeza que muda a
métrica e precisa constar no dicionário da Gold.

### Decomposição da variação de receita (+R$ 12,6 mi)

| Efeito | Valor | Como foi calculado |
|---|---:|---|
| **Volume** | **−R$ 6,3 mi** | (kWh P1 − kWh P0) × preço médio P0 (R$ 0,69/kWh com tributos) |
| **Reajuste tarifário** | **+R$ 11,3 mi** | kWh P1 × (tarifa base P1 − tarifa base P0) |
| **Bandeiras** | **+R$ 7,4 mi** | kWh P1 × adicional médio de bandeira em P1 (em P0 foi zero) |
| Resíduo (mix) | +R$ 0,1 mi | |
| Total | +R$ 12,6 mi | |

A separação usa o modelo **tarifa = tarifa base da classe + adicional da
bandeira**, que reproduz `valor_energia` com erro médio de 0,2%. O adicional
é igual para todas as classes: amarela +R$ 0,0189/kWh, vermelha P1
+R$ 0,0446/kWh e vermelha P2 +R$ 0,0788/kWh (sem tributos).

Em P0 todos os meses foram de bandeira verde; em P1 houve 4 meses verdes,
3 amarelos, 3 de Vermelha P1 e 2 de Vermelha P2. O preço explica toda a alta
da receita, e sem a queda de volume ela teria subido ~12%.

Os reajustes entram em maio de cada ano (mai/2023, mai/2024, mai/2025,
mai/2026), com um ajuste extra da tarifa residencial em jan/2026. O acumulado
varia por classe: Residencial +10,5%, Comercial e Poder Público +18,9%,
Rural +27,4% e Industrial **−1,1%**. A tarifa industrial caiu 12,4% em
mai/2025 e 5,2% em mai/2026, o que fez a receita industrial cair 8,6% no
último ano.

No último ano (jul/25–jun/26 contra jul/24–jun/25), a receita já **caiu
1,25%**: volume −R$ 1,6 mi, reajuste −R$ 3,2 mi (corte industrial) e
bandeiras +R$ 2,5 mi.

### Onde e por que o volume caiu

| Grupo de UCs | kWh P0 | kWh P1 | Variação | Receita perdida (preço P0) |
|---|---:|---:|---:|---:|
| Com **geração distribuída** (3.510) | 18,3 GWh | 7,2 GWh | **−61%** (−11,1 GWh) | −R$ 7,7 mi |
| Com **fraude confirmada** em inspeção (871) | 5,1 GWh | 2,5 GWh | **−51%** (−2,6 GWh) | −R$ 1,8 mi |
| Demais (~40.600) | 203,7 GWh | 208,3 GWh | **+2,3%** (+4,6 GWh) | +R$ 3,2 mi |

- **Sem GD e sem fraude, o volume teria crescido 2,3%.** A queda não é
  perda de clientes nem retração do consumo: é energia que deixou de passar
  pelo medidor da distribuidora.
- **GD** (correlação GD × queda de consumo): após a conexão, a queda mensal
  de consumo de cada UC equivale a ~91% da energia injetada declarada
  (correlação 0,86). As conexões vêm desacelerando (1.038 no 1º semestre de
  2024, 361 no 1º semestre de 2026), mas o estoque de 3.510 UCs (≈31,9 MWp)
  já tira ~11 GWh/ano do faturamento.
- **Fraude**: concentrada em **4 bairros** — Iputinga e Macaxeira (Recife),
  Jardim Jordão e Prazeres (Jaboatão) —, que reúnem 96% das 871
  irregularidades confirmadas. O consumo dessas UCs caiu em mai–jun/2025 e
  só se recuperou parcialmente após a inspeção.
- **Por classe**:

  | Classe | Receita | Volume | Composição da variação de volume |
  |---|---:|---:|---|
  | Comercial | +6,7% | **−10,2%** | GD −4,7 GWh; fraude −1,7 GWh; demais +1,1 GWh |
  | Residencial | +6,9% | **−5,5%** | GD −6,5 GWh; fraude −0,9 GWh; demais +2,9 GWh |
  | Industrial | +8,6% | +0,6% | Sem GD e quase sem fraude |
  | Poder Público | +21,7% | +2,3% | — |
  | Rural | +29,1% | +2,4% | — |

- **Por bairro** (residencial, maior perda de volume em P1 vs P0): Iputinga
  −499 MWh (−22%), Jardim Jordão −440 MWh (−22%), Macaxeira −234 MWh (−22%),
  Prazeres −215 MWh (−19%). Em todos, ~2/3 da perda vem de fraude e ~1/3 de GD; as demais UCs do bairro crescem levemente.
- **Por município**: Jaboatão tem a maior queda de volume (−6,8%) e a menor
  alta de receita (+4,8%). A receita comercial de Jaboatão **caiu** 2,1%
  (fraude −R$ 554 mil e GD −R$ 601 mil, contra +R$ 1,0 mi das demais UCs).

### Recomendações que os dados sustentam

O diagnóstico completo, com as recomendações priorizadas, está em
[../diagnostico_receita.md](../diagnostico_receita.md).

| Alavanca | Evidência | Ordem de grandeza |
|---|---|---|
| Regularizar e cobrar as fraudes já encontradas | 871 UCs, `kwh_recuperado` total de 1,47 GWh; consumo ainda em ~50% da base | ~R$ 1,1 mi de recuperação + até ~R$ 2,0 mi/ano de faturamento ao normalizar o consumo |
| Varredura dirigida nos 4 bairros e nas UCs com queda abrupta | Fila com 92% de acerto (seção 4) | Cada UC fraudadora deixa de faturar ~R$ 2,3 mil/ano |
| Tratar GD como tendência estrutural nas projeções e na estratégia comercial | −61% de volume nas UCs com GD | ~R$ 8,7 mi/ano a preços atuais; cresce ~400–800 UCs/semestre |
| Não contar com bandeira como receita recorrente | +R$ 7,4 mi de bandeiras em P1; sem elas, a receita cresceria só 3,2% | Volátil: depende do custo de geração definido pela ANEEL |

A inadimplência **não** explica a variação: o valor em aberto ficou em
~5,5% do faturado nos dois períodos.

### Gold sugerida

`gold_receita_volume_mensal` no grão (competência × município × bairro ×
classe × flag_gd × flag_fraude), com kWh, receita, receita na tarifa verde e
tarifa vigente. É o que o portal precisa para o drill-down e o que a IA
precisa para perguntas como "qual bairro mais perdeu volume residencial?".

## 3. Visão 360 da UC — Camila Barreto, Gerente de Atendimento

> "Tem que aparecer tudo numa tela só: quem é o cliente, o consumo dos últimos
> meses ao lado do mesmo período do ano passado, as faturas em aberto, o
> medidor instalado, se ele tem painel solar, se a rua dele teve falta de luz
> e os chamados que ele já abriu."

Requisito atendido: user story do atendente (visão única, inclusive
reclamação de conta alta).

| Bloco da tela | Fonte | Regra |
|---|---|---|
| Quem é o cliente | `unidades_consumidoras` | Busca por `id_uc` (número na conta); nome, classe/subgrupo, endereço; CPF/CNPJ mascarado |
| Consumo × mesmo período do ano anterior | `leituras` | Últimos 12 meses ao lado de `mes_referencia − 12`; sinalizar `ESTIMADA` e meses de troca de medidor |
| Faturas em aberto | `faturas` | `status = 'EM ABERTO'`, valor, vencimento e dias de atraso; bandeira de cada mês |
| Medidor instalado | `medidores` | Registro `ATIVO`: modelo, tipo (smart ou não), data de instalação; histórico de trocas |
| Painel solar | `geracao_distribuida` | Potência, modalidade, data de conexão e injeção média |
| Falta de luz na rua | `ocorrencias_rede` | Ocorrências do **mesmo `alimentador`** da UC nos últimos N dias — não só as da própria `id_uc` |
| Chamados anteriores | `atendimentos` + `historico` | Protocolos, assunto, nota, linha do tempo das tratativas |

### "A conta veio alta": o que os dados mostram

- Nas reclamações de `FATURA / VALOR ALTO`, só **~20%** das UCs tiveram
  consumo mais de 10% acima do mesmo mês do ano anterior. 63% estavam
  estáveis (±10%) e 17% consumiram menos.
- Essa distribuição é igual à de um grupo de controle (chamados de
  `LIGACAO NOVA`), e a bandeira da última fatura também segue a média geral.
  Nos dados, **a reclamação não está associada a aumento real de consumo**.
- Por isso a tela deve separar visualmente as três causas possíveis de uma
  conta maior: **consumo** (kWh × ano anterior), **bandeira** do mês e
  **reajuste** da tarifa. Assim o atendente responde "seu consumo não subiu;
  a conta subiu por causa da bandeira vermelha" com base em dados.
- Para UCs com GD, o consumo exibido é líquido; uma "conta alta" pode
  coincidir com meses de baixa geração.

### Gold sugerida

`gold_uc_360` (1 linha por UC, com atributos atuais e indicadores-resumo) e
`gold_uc_consumo_mensal` (UC × competência, com kWh, kWh do ano anterior,
valor, bandeira, status da fatura e tipo de leitura).

## 4. Fila de inspeção — Rafael Coutinho, Gerente de Perdas

> "Pouco mais da metade [das inspeções] encontra alguma irregularidade. Quero
> [...] uma fila das unidades suspeitas, da mais promissora para a menos
> promissora, com o motivo da suspeita e quanta energia dá para recuperar."

Requisitos atendidos: fila priorizada com motivo e energia a recuperar;
ordens de inspeção e registro do resultado; exportar a fila e subir a
planilha de campo (diferenciais).

### Sinais de suspeita validados contra o resultado das inspeções

| Sinal | Fonte | Poder de separação | Observação |
|---|---|---|---|
| **Queda de consumo** em relação ao histórico da própria UC | `leituras` | AUC 0,92; UCs inspecionadas com queda > 10% (sem GD) tiveram **92% de acerto**, contra 8% nas sem queda | O sinal mais forte |
| **Proporção de leituras estimadas** | `leituras.tipo_leitura` | AUC 0,79; 41% nas fraudadoras × 16–21% nas demais | Complementar: o fraudador costuma impedir a leitura |
| **Localização** (bairro/alimentador) | `unidades_consumidoras` | 96% das fraudes em 4 bairros | Prioriza rotas de campo |
| **Classe** | `unidades_consumidoras` | Comercial 84% de acerto, Residencial 56% | |
| **Tipo de medidor** | `medidores` | Nos 4 bairros: `ELETROMECANICO` 92% de acerto × `ELETRONICO` 12,5% | Fora desses bairros não separa (5–9%); usar combinado com a localização |
| **Não ter GD** | `geracao_distribuida` | 3.510 UCs com GD caem ~61% por motivo legítimo | **Excluir ou descontar a injeção declarada**; sem isso a fila seria inundada por falsos positivos |

O acerto observado hoje é de 62,7% (o "pouco mais da metade" do gerente).
Uma fila ordenada por queda de consumo, sem UCs com GD, teria acertado ~92%
nas mesmas inspeções.

### Energia a recuperar

`kwh_recuperado` das inspeções confirmadas equivale a **~6 vezes a queda
mensal de consumo** da UC (mediana 5,9; correlação 0,92). Estimativa simples
para a fila: **energia a recuperar ≈ (consumo de referência − consumo atual) ×
meses desde o início da queda**, calibrada pelo histórico. Isso coincide com a
cronologia: a queda começa ~4–5 meses antes da inspeção.

### Tamanho da fila hoje

Entre as UCs ainda **não inspecionadas** e sem GD, há 102 com queda > 30% e
174 com queda > 20% (P1 vs P0) — menos de um mês da capacidade da equipe
(200+ inspeções/mês). Além disso, as 871 UCs já confirmadas seguem com
consumo em ~50% do histórico: vale acompanhar reincidência.

### Gold sugerida

`gold_fila_inspecao` (UC, score, motivos, kWh e R$ estimados a recuperar,
status) e `gold_inspecoes` (histórico normalizado). As ordens de inspeção e os
resultados registrados no portal são dados **novos**, de escrita do backend,
e não fazem parte do pipeline de leitura.

## 5. Continuidade (DEC/FEC) — Beatriz Farias, Gerente de Operação

> "Quero acompanhar esses indicadores por alimentador ao longo do tempo e
> identificar os piores, para direcionar a manutenção preventiva."

Requisitos atendidos: cálculo de DEC/FEC por alimentador (engenharia de
dados) e acompanhamento no portal.

### Cálculo com estes dados

O case define que **cada registro de `ocorrencias_rede` é uma UC
interrompida**. Para um conjunto (alimentador) e período:

- **DEC** (horas) = Σ `duracao_min` / 60 ÷ nº de UCs do alimentador
- **FEC** (vezes) = nº de ocorrências ÷ nº de UCs do alimentador

O denominador vem de `unidades_consumidoras` (UCs por `alimentador`). Todas as
ocorrências duram ≥ 5 min, então nenhuma fica abaixo do limite de 3 min de
interrupção longa do PRODIST.

| Período | DEC (h) | FEC |
|---|---:|---:|
| 2023 | 1,49 | 0,90 |
| 2024 | 1,50 | 0,90 |
| 2025 | **3,39** | **1,27** |
| Últimos 12 meses | 3,45 | 1,31 |

### Pontos de atenção para a análise

- **Jul/2025** sozinho tem DEC de 1,94 h (contra ~0,13 h num mês normal),
  concentrado no `ALM-REC-008` (7.181 ocorrências em 2025, 96% climáticas).
  Avaliar e documentar se o evento será tratado como expurgável (dia crítico /
  situação de emergência), mostrando os indicadores com e sem ele.
- **O tamanho do alimentador domina o ranking.** Cada alimentador tem
  ~300–400 ocorrências/ano, independentemente de ter 20 ou 2.285 UCs. Por
  isso os "piores" DEC são de alimentadores pequenos (`ALM-JAB-016`, 20 UCs:
  DEC 43,9 h; `ALM-SAO-001`, 32 UCs: 24,3 h). Para priorizar a manutenção,
  exibir junto o **CHI** (horas × UCs interrompidas = Σ duração) e o volume de
  ocorrências por causa (vegetação e falha de equipamento são acionáveis; a
  causa climática, não).
- Os valores são comparativos entre alimentadores e períodos, não com os
  limites regulatórios reais (o próprio case faz essa ressalva).

### Gold sugerida

`gold_continuidade_alimentador_mensal` (alimentador × mês: ocorrências, horas,
UCs, DEC, FEC, CHI, distribuição por causa e flag de evento atípico).

## 6. Indicadores gerais — visão da diretoria

User story: "ver os principais indicadores do negócio e compará-los entre
períodos". Métricas e fontes:

| Indicador | Fonte | Observação |
|---|---|---|
| Receita faturada e arrecadada | `faturas` | Arrecadada = `status = PAGA` |
| Volume faturado (kWh) | `leituras` | Com o tratamento da troca de medidor |
| Tarifa média e efeito bandeira | `faturas` + `leituras` | |
| Inadimplência (% do valor em aberto) | `faturas` | ~5,5% do valor faturado; em número de faturas, maior em Poder Público (11%) e Residencial (8,5%) |
| UCs ativas, UCs com GD, potência instalada | cadastro + `geracao_distribuida` | |
| DEC/FEC | `ocorrencias_rede` | |
| Volume de atendimentos e satisfação | `atendimentos` | Nota cai para 3,1 quando o atendimento passa de 14 dias |
| Inspeções e taxa de acerto | `inspecoes` | |

## 7. Agente de IA (Text-to-SQL) e insights — Patrícia Lins, Diretora de Tecnologia

> "Quantas unidades com painel solar em Olinda tiveram queda de consumo acima
> de 30%? [...] Se o agente não souber, ele tem que dizer que não sabe."

Requisitos atendidos: perguntas em português, termos do dia a dia, respostas
auditáveis, insights embutidos, IA sem permissão de escrita.

### Vocabulário do dia a dia → dados

| O usuário diz | Significa nos dados |
|---|---|
| "conta de luz", "conta" | `faturas` (`valor_total`; por competência) |
| "conta atrasada", "inadimplência" | `faturas.status = 'EM ABERTO'` |
| "consumo", "quanto gastou de energia" | `leituras.consumo_kwh` (kWh) |
| "mês da conta", "competência" | `mes_referencia` |
| "falta de luz", "apagão", "queda de energia" | `ocorrencias_rede.tipo = 'FALTA DE ENERGIA'` (evento na rede) e/ou `atendimentos.assunto = 'FALTA DE ENERGIA'` (reclamação). O agente deve dizer qual das duas usou |
| "painel solar", "energia solar" | `geracao_distribuida` |
| "gato", "furto", "fraude" | `inspecoes` com irregularidade confirmada |
| "bandeira vermelha" | `bandeira_tarifaria IN ('Vermelha P1', 'Vermelha P2')` |
| "medidor inteligente" | `medidores.tipo = 'SMART'` |
| "rua", "região" (falta de luz) | `alimentador` (proxy da rua; não há dado de logradouro na ocorrência) |
| "último ano" | Últimos 12 meses até jun/2026 — o agente deve explicitar o período usado |

### Exemplos das lideranças já respondíveis com os dados

| Pergunta | Resposta (exploratória) | Tabela que viabiliza |
|---|---|---|
| "Quantas UCs com painel solar em Olinda tiveram queda de consumo acima de 30%?" | 327 das 328 (antes × depois da conexão) | Consumo por UC com flag de GD |
| "Qual bairro mais perdeu volume residencial no último ano?" | Iputinga (Recife): −351 MWh (−16,7%) vs o ano anterior | `gold_receita_volume_mensal` |
| "Quanto a receita comercial cresceu em Jaboatão?" | Não cresceu: −5,1% vs o ano anterior e −2,1% vs P0 | `gold_receita_volume_mensal` |

As perguntas são ambíguas quanto ao período ("último ano" contra qual
base?). O agente deve declarar o período e a métrica na resposta: isso
torna a resposta auditável e evita números diferentes para a mesma pergunta.

### Limites que o agente deve conhecer (para dizer "não sei")

- Período coberto: jul/2022 a jun/2026. Inspeções: só ago–dez/2025. GD: só
  conexões a partir de 2024.
- Não há tarifa explícita: o preço é derivado de `valor_energia / consumo`.
- A injeção de GD é uma média mensal declarada, não uma série mensal.
- `nota_satisfacao` nula significa "não avaliou", e não nota zero.
- Ocorrências e atendimentos **não** se ligam evento a evento (ver
  [relacionamentos.md](relacionamentos.md#ocorrências--atendimentos)); só
  em agregados por mês e região.
- Dados pessoais (nome, CPF) não devem ser expostos pelo agente.

### Insights embutidos sugeridos

- Tela de receita: texto gerado a partir da decomposição volume/reajuste/
  bandeira do período filtrado.
- Visão 360: "o consumo deste mês está X% acima/abaixo do mesmo mês do ano
  passado; a fatura subiu por causa da bandeira".
- Fila de perdas: motivo da suspeita em linguagem natural a partir das
  features (queda, leituras estimadas, bairro).

Para garantir fidelidade, o insight deve ser gerado **a partir de números
já calculados na Gold** e exibidos ao lado, nunca calculados pelo modelo.

## 8. Requisitos de engenharia de dados (5.2.1) × estes documentos

| Requisito | Onde está a base |
|---|---|
| Bronze preservando o original (8 arquivos) | Formatos e particularidades de leitura: [qualidade_dados.md](qualidade_dados.md#leitura-dos-arquivos) (`;` nas faturas, 3 abas no Excel, JSON aninhado, ler tudo como texto) |
| Silver confiável, com problemas tratados | Catálogo e regras: [qualidade_dados.md](qualidade_dados.md) e a seção "Qualidade" de cada fonte |
| Integridade referencial medição × faturamento × cadastro | [relacionamentos.md](relacionamentos.md#integridade-referencial): 32.285 faturas e 8.609 leituras órfãs |
| Gold modelada pelas perguntas de negócio | Seções 2–7 deste documento ("Gold sugerida") |
| DEC/FEC conforme a ANEEL | Seção 5 |
| Dicionário de dados da Gold com decisões de limpeza | Tabela abaixo |
| Testes de qualidade automatizados (diferencial) | [qualidade_dados.md](qualidade_dados.md#validações-recomendadas-para-a-silver-testes-de-dados) |

### Decisões de limpeza que alteram métricas de negócio

Devem constar no dicionário da Gold, porque mudam números que a diretoria vê:

| Decisão | Métrica afetada | Impacto se não tratada |
|---|---|---|
| Excluir faturas órfãs (`FTX…`, UC inexistente) | Receita | +R$ 10,2 mi (+1,5%) de receita inexistente |
| Converter `valor_total` no formato `R$ 1.234,56` | Receita | −9% da receita, se esses valores virarem nulo |
| Excluir leituras `LTX…` duplicadas | Volume | Dupla contagem de 8.609 leituras |
| Imputar o consumo dos meses de troca de medidor | Volume | Queda de −5,1% em vez de −4,0% |
| Corrigir consumo com sinal invertido | Volume | ~1.700 leituras negativas somadas ao total |
| Interpretar `MM-DD-AAAA` corretamente | Séries por data (emissão, leitura, inspeção) | Dia e mês trocados em silêncio |
| Separar UCs com GD na análise de perdas | Fila de inspeção | 3.510 falsos positivos |
| Tratar jul/2025 como evento atípico (ou não) | DEC/FEC | DEC 2025 de 3,39 h, contra ~1,5 h nos anos normais |
| Corrigir encoding dos bairros | Recortes por bairro | 59 nomes duplicados (ex.: `Jardim JordÃ£o`), dividindo o volume do mesmo bairro |

## 9. Suposições a registrar no README

- "Volume faturado" = soma de `consumo_kwh` das leituras com fatura
  correspondente; "receita" = `valor_total` (com tributos), por competência.
- UCs com fraude = inspeções com irregularidade confirmada; UCs não
  inspecionadas não são classificadas como fraudadoras.
- A troca de medidor é identificada por `leitura_atual < leitura_anterior`
  com consumo negativo.
- A tarifa vigente é derivada dos meses de bandeira verde e mantida até o
  próximo reajuste.
