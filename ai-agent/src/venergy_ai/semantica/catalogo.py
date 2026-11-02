"""Catálogo das views de `ai_read`: o que o agente pode consultar e como ler cada coluna.

As views ficam em `importador/views.sql`. O teste de integração compara este catálogo
com as colunas reais das views, nos dois sentidos, e falha quando uma muda sem a outra.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Coluna:
    nome: str
    descricao: str
    unidade: str | None = None


@dataclass(frozen=True)
class Visao:
    nome: str
    descricao: str
    grao: str
    chave: tuple[str, ...]
    colunas: tuple[Coluna, ...]
    # Coluna que situa a linha no tempo; None quando a view é um retrato atual.
    coluna_tempo: str | None
    periodo: str
    regras: tuple[str, ...] = ()

    def coluna(self, nome: str) -> Coluna:
        for coluna in self.colunas:
            if coluna.nome == nome:
                return coluna
        raise KeyError(f'{self.nome}.{nome}')


COMPETENCIA = Coluna('competencia', 'Competência: primeiro dia do mês de referência.')
ID_UC = Coluna('id_uc', 'Identificador da unidade consumidora (UC), no formato UC + 6 dígitos.')
ALIMENTADOR = Coluna('alimentador', 'Alimentador, no formato ALM-AAA-999.')
CLASSE = Coluna(
    'classe', 'Classe da UC: Residencial, Comercial, Industrial, Rural ou Poder Público.'
)
GRUPO_UC = Coluna(
    'grupo_uc',
    'Grupo de UC na competência: GD (desde o mês da conexão), IRREGULARIDADE_CONFIRMADA '
    '(desde o mês da primeira inspeção com irregularidade confirmada) ou DEMAIS. '
    'A precedência é GD > IRREGULARIDADE_CONFIRMADA > DEMAIS.',
)

VISOES = (
    Visao(
        nome='ucs',
        descricao='Cadastro atual das UCs, sem titular, documento e endereço.',
        grao='UC',
        chave=('id_uc',),
        colunas=(
            ID_UC,
            Coluna('municipio', 'Município da UC.'),
            Coluna('bairro', 'Bairro da UC.'),
            CLASSE,
            ALIMENTADOR,
            Coluna('flag_gd', 'A UC tem geração distribuída (GD) conectada.'),
            Coluna(
                'flag_irregularidade_confirmada',
                'A UC já teve inspeção com irregularidade confirmada.',
            ),
        ),
        coluna_tempo=None,
        periodo='Retrato do cadastro na carga mais recente.',
        regras=('Para recortar outra view por município, bairro ou classe, junte por id_uc.',),
    ),
    Visao(
        nome='uc_consumo_faturamento_mensal',
        descricao='Consumo, fatura, leitura e pagamento de cada UC em cada competência.',
        grao='UC × competência',
        chave=('id_uc', 'competencia'),
        colunas=(
            ID_UC,
            COMPETENCIA,
            Coluna(
                'consumo_kwh_original',
                'Consumo original, como veio da medição. Só para auditoria.',
                'kWh',
            ),
            Coluna(
                'consumo_kwh_analitico',
                'Consumo analítico, o usado em todas as análises: igual ao original, exceto '
                'na troca de medidor, quando é estimado pela mediana da UC.',
                'kWh',
            ),
            Coluna(
                'metodo_consumo',
                'Origem do consumo analítico: LEITURA_UTILIZAVEL, MEDIANA_FASE_UC ou '
                'MEDIANA_HISTORICA_UC.',
            ),
            Coluna('tipo_leitura', 'REAL ou ESTIMADA (leitura feita sem acesso ao medidor).'),
            Coluna('flag_troca_medidor', 'Houve troca de medidor na competência.'),
            Coluna('id_fatura', 'Fatura da competência. Nulo quando não houve fatura emitida.'),
            Coluna(
                'volume_faturado_kwh',
                'Volume faturado na fatura da competência. Zero sem fatura.',
                'kWh',
            ),
            Coluna(
                'valor_total',
                'Valor da fatura, com tributos (a "conta de luz"). Zero sem fatura.',
                'R$',
            ),
            Coluna(
                'valor_arrecadado',
                'Valor pago da fatura: igual ao total quando PAGA, zero quando ABERTA.',
                'R$',
            ),
            Coluna('tarifa_base', 'Tarifa base da fatura. Nula sem fatura.', 'R$/kWh'),
            Coluna(
                'adicional_bandeira',
                'Adicional da bandeira tarifária. Nulo sem fatura.',
                'R$/kWh',
            ),
            Coluna(
                'bandeira',
                'Bandeira tarifária: VERDE, AMARELA, VERMELHA_P1 ou VERMELHA_P2. Nula sem fatura.',
            ),
            Coluna(
                'status_pagamento',
                'PAGA ou ABERTA (conta em aberto). Nulo sem fatura.',
            ),
            Coluna('data_vencimento', 'Vencimento da fatura. Nulo sem fatura.'),
            GRUPO_UC,
        ),
        coluna_tempo='competencia',
        periodo='Competências de jul/2022 a jun/2026.',
        regras=(
            'Para consumo, use consumo_kwh_analitico. consumo_kwh_original só serve para '
            'auditoria.',
            'Competência sem fatura tem id_fatura nulo e valores zerados. Para valores de '
            'fatura, filtre id_fatura IS NOT NULL.',
        ),
    ),
    Visao(
        nome='receita_volume_mensal',
        descricao='Receita, receita arrecadada e volume faturado por segmento e competência.',
        grao='competência × município × bairro × classe × grupo de UC',
        chave=('competencia', 'municipio', 'bairro', 'classe', 'grupo_uc'),
        colunas=(
            COMPETENCIA,
            Coluna('municipio', 'Município do segmento.'),
            Coluna('bairro', 'Bairro do segmento.'),
            CLASSE,
            GRUPO_UC,
            Coluna('volume_faturado_kwh', 'Volume faturado do segmento.', 'kWh'),
            Coluna('receita', 'Receita faturada do segmento, com tributos.', 'R$'),
            Coluna('receita_arrecadada', 'Parte da receita em faturas pagas.', 'R$'),
            Coluna(
                'componente_tarifa_reais',
                'Parte da receita da tarifa base (volume × tarifa base), sem tributos.',
                'R$',
            ),
            Coluna(
                'componente_bandeira_reais',
                'Parte da receita do adicional de bandeira (volume × adicional), sem tributos.',
                'R$',
            ),
        ),
        coluna_tempo='competencia',
        periodo='Competências de jul/2022 a jun/2026.',
        regras=(
            'Para receita e volume de um recorte, some as linhas; não tire média de segmentos.',
            'Tarifa média = SUM(receita) ÷ SUM(volume_faturado_kwh).',
            'Inadimplência = (receita − receita arrecadada) ÷ receita do período.',
        ),
    ),
    Visao(
        nome='gd_uc',
        descricao='UCs com geração distribuída (GD, painel solar) conectada.',
        grao='UC com GD',
        chave=('id_uc',),
        colunas=(
            ID_UC,
            Coluna('potencia_kw', 'Potência instalada.', 'kW'),
            Coluna('data_conexao', 'Data de conexão da GD.'),
        ),
        coluna_tempo='data_conexao',
        periodo='Conexões de jan/2024 a jun/2026.',
        regras=(
            'Antes × depois da GD de uma UC: compare as competências anteriores e posteriores '
            'ao mês de data_conexao.',
        ),
    ),
    Visao(
        nome='medidores_historico',
        descricao='Medidores que cada UC teve, com instalação e retirada.',
        grao='instalação de medidor',
        chave=('id_medidor', 'data_instalacao'),
        colunas=(
            Coluna('id_medidor', 'Identificador do medidor.'),
            ID_UC,
            Coluna('data_instalacao', 'Data de instalação do medidor na UC.'),
            Coluna('data_retirada', 'Data de retirada. Nula se o medidor está instalado.'),
            Coluna('tipo_medidor', 'Tecnologia do medidor: ELETRONICO, ELETROMECANICO ou SMART.'),
        ),
        coluna_tempo='data_instalacao',
        periodo='Instalações ao longo de toda a base.',
        regras=('Medidor atual da UC: data_retirada IS NULL.',),
    ),
    Visao(
        nome='continuidade_alimentador_mensal',
        descricao='CHI, interrupções, DEC e FEC de cada alimentador em cada competência.',
        grao='alimentador × competência',
        chave=('alimentador', 'competencia'),
        colunas=(
            ALIMENTADOR,
            COMPETENCIA,
            Coluna(
                'numero_ucs',
                'UCs do alimentador no cadastro, o mesmo número em todas as competências.',
                'UCs',
            ),
            Coluna(
                'chi_horas',
                'CHI: horas sem energia somadas sobre as UCs interrompidas, sem contar duas '
                'vezes as sobrepostas.',
                'UC × hora',
            ),
            Coluna(
                'interrupcoes',
                'Interrupções: ocorrências que não começaram com a UC já sem energia.',
                'interrupções',
            ),
            Coluna('dec', 'DEC do mês: chi_horas ÷ numero_ucs.', 'horas/UC'),
            Coluna('fec', 'FEC do mês: interrupcoes ÷ numero_ucs.', 'interrupções/UC'),
            Coluna(
                'causa',
                'Causa principal do mês (a de mais minutos); SEM OCORRENCIA no mês sem '
                'interrupção.',
            ),
            Coluna(
                'flag_evento_atipico',
                'A competência é de evento atípico para o alimentador (ex.: o evento climático '
                'de jul/2025).',
            ),
        ),
        coluna_tempo='competencia',
        periodo='Competências de jul/2022 a jun/2026, todo alimentador em todo mês.',
        regras=(
            'Nunca some nem tire média de dec ou fec. DEC de um período: SUM(chi_horas) ÷ '
            'numero_ucs. Para vários alimentadores, divida pela soma do numero_ucs de cada '
            'alimentador, contado uma vez.',
            'Critério padrão para os piores alimentadores: CHI.',
            'Sem o evento atípico: filtre NOT flag_evento_atipico antes de somar.',
            'Por causa, use ocorrencias_uc: causa aqui é só a principal do mês.',
        ),
    ),
    Visao(
        nome='ocorrencias_uc',
        descricao='Cada interrupção de energia percebida por uma UC.',
        grao='ocorrência por UC',
        chave=('id_ocorrencia',),
        colunas=(
            Coluna('id_ocorrencia', 'Identificador da ocorrência.'),
            ID_UC,
            ALIMENTADOR,
            Coluna('data_abertura', 'Início da interrupção, hora local.'),
            Coluna('data_encerramento', 'Fim da interrupção, hora local.'),
            Coluna('duracao_min', 'Duração registrada.', 'min'),
            Coluna(
                'duracao_efetiva_min',
                'Duração sem os minutos em que a UC já estava sem energia por outra ocorrência.',
                'min',
            ),
            Coluna(
                'causa',
                'Causa: CLIMATICA, VEGETACAO, TERCEIROS, SOBRECARGA, FALHA DE EQUIPAMENTO, '
                'NAO IDENTIFICADA ou NAO INFORMADA.',
            ),
            Coluna(
                'flag_sobreposicao',
                'Começou com a UC já sem energia: não é interrupção nova.',
            ),
        ),
        coluna_tempo='data_abertura',
        periodo='Aberturas de jul/2022 a jun/2026.',
        regras=(
            'Tempo sem energia: SUM(duracao_efetiva_min). Número de interrupções: linhas com '
            'NOT flag_sobreposicao.',
        ),
    ),
    Visao(
        nome='atendimentos',
        descricao='Protocolos de atendimento das UCs (reclamações e pedidos).',
        grao='protocolo',
        chave=('protocolo',),
        colunas=(
            Coluna('protocolo', 'Número do protocolo.'),
            ID_UC,
            Coluna('aberto_em', 'Abertura do protocolo, hora local.'),
            Coluna(
                'assunto',
                'Assunto: FALTA DE ENERGIA, FATURA, DANO ELETRICO, LIGACAO NOVA, '
                'GERACAO DISTRIBUIDA ou RELIGACAO.',
            ),
            Coluna('status', 'Situação do protocolo (ex.: ENCERRADO, EM ABERTO).'),
            Coluna('nota', 'Nota de satisfação de 0 a 10. Nula quando o titular não avaliou.'),
        ),
        coluna_tempo='aberto_em',
        periodo='Aberturas de jul/2022 a jun/2026.',
        regras=(
            'Nota nula é "não avaliou": fica fora da média, nunca conta como zero.',
            'O assunto GERACAO DISTRIBUIDA não indica que a UC tem GD; para isso, use gd_uc.',
        ),
    ),
    Visao(
        nome='atendimentos_historico',
        descricao='Datas das tratativas de cada protocolo, sem o texto.',
        grao='protocolo × sequência',
        chave=('protocolo', 'sequencia'),
        colunas=(
            Coluna('protocolo', 'Número do protocolo.'),
            Coluna('sequencia', 'Ordem da tratativa no protocolo, a partir de 1.'),
            Coluna('data', 'Data e hora da tratativa.'),
        ),
        coluna_tempo='data',
        periodo='Tratativas dos protocolos de atendimentos.',
        regras=('Tempo até a primeira tratativa: MIN(data) do protocolo − aberto_em.',),
    ),
    Visao(
        nome='inspecoes',
        descricao='Inspeções de campo já feitas: as históricas e as concluídas no portal.',
        grao='inspeção',
        chave=('id_inspecao',),
        colunas=(
            Coluna('id_inspecao', 'Identificador da inspeção.'),
            ID_UC,
            Coluna('data', 'Data da inspeção.'),
            Coluna('inspetor', 'Código do inspetor (ex.: INSP-001).'),
            Coluna('resultado', 'IRREGULARIDADE CONFIRMADA ou SEM IRREGULARIDADE.'),
            Coluna(
                'tipo_irregularidade',
                'Tipo da irregularidade confirmada (texto livre). Nulo sem irregularidade.',
            ),
            Coluna('kwh_recuperado', 'Energia recuperada apurada na inspeção.', 'kWh'),
            Coluna('origem', 'historica (base da Gold) ou portal (concluída no portal).'),
        ),
        coluna_tempo='data',
        periodo='Históricas de ago a dez/2025, mais as concluídas no portal.',
        regras=(
            'Taxa de acerto = inspeções com IRREGULARIDADE CONFIRMADA ÷ inspeções do período.',
        ),
    ),
    Visao(
        nome='fila_inspecao',
        descricao='UCs suspeitas sem ordem ativa, com score, motivo e energia a recuperar.',
        grao='UC candidata',
        chave=('id_uc',),
        colunas=(
            ID_UC,
            Coluna('score', 'Pontuação da suspeita: quanto maior, mais promissora.'),
            Coluna('motivos', 'Motivos da suspeita, em lista JSON.'),
            Coluna(
                'energia_recuperar_kwh',
                'Energia a recuperar estimada, caso a irregularidade se confirme.',
                'kWh',
            ),
            Coluna('energia_recuperar_reais', 'Valor estimado da energia a recuperar.', 'R$'),
        ),
        coluna_tempo=None,
        periodo='Retrato da fila na carga mais recente.',
        regras=('Energia a recuperar é estimativa; kwh_recuperado de inspecoes é o apurado.',),
    ),
)

VISOES_POR_NOME = {visao.nome: visao for visao in VISOES}
