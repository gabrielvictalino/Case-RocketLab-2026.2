# V-Energy Grid 360

Plataforma que consolida cadastro, medição, faturamento, rede e atendimento da
V-Energy em torno da unidade consumidora, para o portal, o agente de IA e o
diagnóstico da receita.

## Linguagem

### Cadastro e rede

**Unidade consumidora (UC)**:
O ponto que recebe energia e tem um medidor; entidade central da plataforma. Um mesmo titular pode ter várias UCs.
_Evitar_: cliente, consumidor, instalação

**Classe**:
Categoria tarifária da UC: Residencial, Comercial, Industrial, Rural ou Poder Público.
_Evitar_: tipo de cliente, segmento

**Alimentador**:
Circuito de média tensão que abastece um conjunto de UCs; unidade de análise da continuidade.
_Evitar_: rede, linha, circuito

### Medição

**Consumo analítico**:
Consumo (kWh) de uma competência usado em todas as análises e telas; igual ao consumo original, exceto nos meses de troca de medidor, em que é estimado pelo histórico da UC.
_Evitar_: consumo corrigido, consumo tratado

**Consumo original**:
Consumo (kWh) como veio do sistema de medição, preservado para auditoria.
_Evitar_: consumo bruto

**Leitura estimada**:
Leitura feita sem acesso ao medidor, com consumo estimado pela distribuidora.

**Troca de medidor**:
Competência em que o medidor da UC foi substituído, e por isso o consumo original não representa o consumo real.

### Tempo

**Competência**:
O mês de referência de uma leitura ou fatura, independentemente de quando foi emitida ou paga. É o eixo de tempo de toda a plataforma.
_Evitar_: mês da fatura, mês de emissão, data

**Período**:
Intervalo contínuo de competências escolhido para análise.
_Evitar_: intervalo, janela

**Período de comparação**:
O período contra o qual o período analisado é comparado; por padrão, o mesmo intervalo no ano anterior.
_Evitar_: base, referência

**Primeiro ano (P0)**:
Competências de jul/2022 a jun/2023, a base usada pelo Diretor Comercial.

**Últimos 12 meses (P1)**:
Competências de jul/2025 a jun/2026, as mais recentes da base.
_Evitar_: último ano, ano atual

### Receita

**Receita**:
Valor total faturado nas competências do período, com tributos. Sem qualificativo, receita é sempre a faturada.
_Evitar_: faturamento, receita bruta

**Receita arrecadada**:
Parte da receita cujas faturas foram pagas.
_Evitar_: receita recebida, caixa

**Volume faturado**:
Energia (kWh) das leituras que têm fatura correspondente nas competências do período.
_Evitar_: consumo total, energia vendida

**Efeito-volume**:
Parte da variação de receita entre dois períodos explicada pela mudança na energia faturada, a preços do período de comparação.

**Efeito-preço**:
Parte da variação de receita explicada pela mudança de preço, dividida em reajuste (tarifa base da classe) e bandeira. O que sobra é o efeito-mix.
_Evitar_: efeito-tarifa

**Grupo de UC**:
Recorte que explica a variação de volume: UCs com GD, UCs com irregularidade confirmada e demais.

**Tarifa média**:
Receita dividida pelo volume faturado, em R$/kWh. É derivada; a base não tem tabela de tarifas.
_Evitar_: preço, tarifa

**Inadimplência**:
Percentual da receita do período em faturas ainda em aberto.
_Evitar_: calote, atraso

**Explicação da conta**:
Comparação da fatura de uma UC com a do mesmo mês do ano anterior, separando o que mudou em consumo, bandeira e tarifa. Responde à reclamação de "conta alta".

### Continuidade

**DEC / FEC**:
Duração e frequência equivalentes de interrupção por UC de um alimentador no período. Comparáveis entre alimentadores e períodos, não com os limites regulatórios reais.

**CHI**:
Total de horas de interrupção somadas sobre todas as UCs interrompidas de um alimentador. Critério padrão para priorizar manutenção.
_Evitar_: horas de falta

**Evento atípico**:
Período com interrupções muito acima do normal por causa excepcional (ex.: o evento climático de jul/2025), que pode ser excluído da análise de continuidade.
_Evitar_: expurgo (termo regulatório que não se aplica aqui)

### Perdas

**Inspeção**:
Vistoria de campo já realizada em uma UC, com resultado (irregularidade confirmada ou sem irregularidade), tipo de irregularidade e energia recuperada.
_Evitar_: fiscalização, visita

**Ordem de inspeção**:
Pedido para vistoriar uma UC, criado no portal a partir da fila. Quando concluída, gera uma inspeção.
_Evitar_: OS, chamado, tarefa

**Ordem ativa**:
Ordem de inspeção que ainda não foi concluída nem cancelada. Uma UC tem no máximo uma ordem ativa.

**Fila de inspeção**:
Lista de UCs suspeitas sem ordem ativa, ordenadas da mais para a menos promissora, com o motivo da suspeita e a energia estimada a recuperar.
_Evitar_: lista de suspeitos, ranking de fraude

**Reinspeção**:
Nova ordem de inspeção para uma UC que já tem inspeção anterior.

**Motivo da suspeita**:
Os sinais que colocaram a UC na fila (queda de consumo, leituras estimadas, localização, tipo de medidor), em linguagem do negócio.

**Energia a recuperar**:
Estimativa, em kWh, da energia não faturada que a inspeção pode recuperar se confirmar irregularidade.
_Evitar_: kWh recuperado (esse é o valor real apurado na inspeção)

**Tentativa sem acesso**:
Ida a campo em que a vistoria não pôde ser feita (ex.: imóvel fechado). A ordem volta a aguardar nova ida; não é cancelada nem concluída.

**Taxa de acerto**:
Percentual das inspeções do período que confirmaram irregularidade.
_Evitar_: precisão, assertividade

### Portal

**Insight**:
Texto gerado por IA que interpreta os números exibidos numa tela, citando apenas esses números.
_Evitar_: análise, resumo, recomendação

**Cargo**:
Papel do usuário no portal (diretoria, comercial, atendimento, perdas, operação), que define as telas que ele vê.
_Evitar_: perfil, permissão
