"""Termos do dia a dia e limites dos dados, a partir da seção 7 de `perguntas_negocio.md`.

As referências usam `view` ou `view.coluna` do catálogo. Um teste confere que todas
existem, então renomear uma coluna sem atualizar o vocabulário quebra a suíte.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Termo:
    expressoes: tuple[str, ...]
    significado: str
    referencias: tuple[str, ...]


@dataclass(frozen=True)
class Limite:
    descricao: str
    referencias: tuple[str, ...] = ()


VOCABULARIO = (
    Termo(
        ('conta de luz', 'conta', 'fatura'),
        'Valor da fatura da UC na competência, com tributos. Num recorte (bairro, classe, '
        'município), é a receita.',
        ('uc_consumo_faturamento_mensal.valor_total', 'receita_volume_mensal.receita'),
    ),
    Termo(
        ('conta atrasada', 'conta vencida', 'conta em atraso'),
        "Fatura vencida e não paga: status_pagamento = 'ABERTA' AND data_vencimento antes da "
        'data de referência da carga (informada abaixo). Uma ABERTA que ainda não venceu não '
        'está atrasada.',
        (
            'uc_consumo_faturamento_mensal.status_pagamento',
            'uc_consumo_faturamento_mensal.data_vencimento',
        ),
    ),
    Termo(
        ('conta em aberto', 'conta não paga'),
        "Fatura com status_pagamento = 'ABERTA', vencida ou não.",
        ('uc_consumo_faturamento_mensal.status_pagamento',),
    ),
    Termo(
        ('inadimplência',),
        'Indicador do portal: receita em aberto ÷ receita do período × 100, em %, sem olhar o '
        'vencimento. '
        'Para o valor atrasado de fato, use conta atrasada.',
        ('receita_volume_mensal.receita', 'receita_volume_mensal.receita_arrecadada'),
    ),
    Termo(
        ('consumo', 'quanto gastou de energia', 'gasto de energia'),
        'Consumo analítico da UC, em kWh.',
        ('uc_consumo_faturamento_mensal.consumo_kwh_analitico',),
    ),
    Termo(
        ('energia cobrada', 'quanto foi faturado de energia'),
        'Volume faturado, em kWh.',
        (
            'uc_consumo_faturamento_mensal.volume_faturado_kwh',
            'receita_volume_mensal.volume_faturado_kwh',
        ),
    ),
    Termo(
        ('mês da conta', 'mês de referência'),
        'Competência.',
        ('uc_consumo_faturamento_mensal.competencia',),
    ),
    Termo(
        ('receita', 'faturamento'),
        'Receita faturada, com tributos. A paga é a receita arrecadada.',
        ('receita_volume_mensal.receita', 'receita_volume_mensal.receita_arrecadada'),
    ),
    Termo(
        ('falta de luz', 'apagão', 'queda de energia', 'ficou sem luz'),
        'Pode ser a interrupção na rede (ocorrencias_uc por UC, continuidade_alimentador_mensal '
        'por alimentador) ou a reclamação (atendimentos com assunto FALTA DE ENERGIA). A resposta '
        'diz qual das duas usou.',
        ('ocorrencias_uc', 'continuidade_alimentador_mensal', 'atendimentos.assunto'),
    ),
    Termo(
        ('rua', 'região'),
        'Para falta de luz, o alimentador é a aproximação da rua: a ocorrência não tem '
        'logradouro. Para as demais perguntas, use o bairro.',
        ('ocorrencias_uc.alimentador', 'ucs.bairro'),
    ),
    Termo(
        ('pior alimentador', 'onde fazer manutenção'),
        'Maior CHI no período. DEC e FEC comparam alimentadores de tamanhos diferentes.',
        ('continuidade_alimentador_mensal.chi_horas',),
    ),
    Termo(
        ('temporal de julho', 'evento climático', 'evento atípico'),
        'Competências marcadas com flag_evento_atipico. Para tirar o evento, filtre '
        'NOT flag_evento_atipico.',
        ('continuidade_alimentador_mensal.flag_evento_atipico',),
    ),
    Termo(
        ('painel solar', 'energia solar', 'geração própria'),
        'UC com geração distribuída (GD).',
        ('gd_uc', 'ucs.flag_gd', 'uc_consumo_faturamento_mensal.grupo_uc'),
    ),
    Termo(
        ('gato', 'furto', 'fraude', 'desvio'),
        "Fonte padrão: inspecoes com resultado = 'IRREGULARIDADE CONFIRMADA', que inclui as "
        'confirmadas no portal. ucs.flag_irregularidade_confirmada é o retrato da última carga '
        'e não tem as confirmações do portal feitas depois dela: use só para cruzar com o '
        'cadastro, e diga isso na resposta.',
        ('inspecoes.resultado', 'ucs.flag_irregularidade_confirmada'),
    ),
    Termo(
        ('suspeitos', 'quem inspecionar'),
        'Fila de inspeção: UCs suspeitas sem ordem ativa, da mais para a menos promissora.',
        ('fila_inspecao.score',),
    ),
    Termo(
        ('bandeira vermelha',),
        "bandeira IN ('VERMELHA_P1', 'VERMELHA_P2').",
        ('uc_consumo_faturamento_mensal.bandeira',),
    ),
    Termo(
        ('medidor inteligente', 'smart meter'),
        "tipo_medidor = 'SMART'. O medidor atual da UC tem data_retirada nula.",
        ('medidores_historico.tipo_medidor', 'medidores_historico.data_retirada'),
    ),
    Termo(
        ('nota', 'satisfação', 'avaliação do atendimento'),
        'Nota de 1 a 5 do protocolo, com uma casa decimal. Nula é "não avaliou" e fica fora '
        'da média.',
        ('atendimentos.nota',),
    ),
    Termo(
        ('último ano', 'últimos 12 meses'),
        'Os 12 meses até a competência mais recente. A resposta sempre diz o período usado.',
        (),
    ),
)

# A cobertura da base vem da carga: `descrever_semantica` a escreve na seção da carga.
# Nada aqui cita mês: uma exportação nova pode cobrir outros meses.
LIMITES = (
    Limite(
        'As inspeções históricas cobrem só parte da base. A cobertura do histórico sai de '
        "MIN(data) e MAX(data) de inspecoes com origem = 'historica'. Esse limite vale só "
        "para o histórico: inspeções com origem = 'portal' podem existir fora dele e "
        'entram na taxa de acerto do período solicitado. Consulte as inspeções da origem '
        'pedida; sem origem explícita, inclua ambas. Só não há taxa quando não há '
        'inspeções no recorte (denominador zero).',
        ('inspecoes.origem', 'inspecoes.data'),
    ),
    Limite(
        'Não há geração nem injeção de energia da GD: só a potência instalada e a data de conexão.',
        ('gd_uc',),
    ),
    Limite(
        'Nota nula é "não avaliou", nunca zero.',
        ('atendimentos.nota',),
    ),
    Limite(
        'Ocorrências e atendimentos não se ligam evento a evento. Só dá para cruzar agregados '
        'por competência e por alimentador ou bairro.',
        ('ocorrencias_uc', 'atendimentos'),
    ),
    Limite(
        'Não há nome, CPF, CNPJ, endereço nem o texto dos atendimentos. Pedido desses dados '
        'recebe "não sei".',
        ('ucs', 'atendimentos_historico'),
    ),
    Limite(
        'O cadastro e a fila de inspeção são retratos da carga mais recente, sem histórico.',
        ('ucs', 'fila_inspecao'),
    ),
)
