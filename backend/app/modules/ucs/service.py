import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from app.core.decomposicao import decompor
from app.core.errors import APIError
from app.modules.perdas.schemas import Ordem
from app.modules.ucs import repository as repo
from app.modules.ucs.schemas import (
    Cabecalho,
    Chamado,
    ChamadoHistorico,
    Consumo,
    EfeitosConta,
    ExplicacaoConta,
    FaturaAberta,
    FaturaComparada,
    GD,
    Inspecao,
    Interrupcoes,
    MedidorAtual,
    MesConsumo,
    OcorrenciaUC,
    PontoConsumo,
    ResumoAlimentador,
    VisaoUC,
)


def normalizar_id_uc(bruto: str) -> str:
    limpo = bruto.strip()
    match = re.fullmatch(r'(?i)(?:uc)?(\d{6})', limpo)
    if not match:
        raise APIError(422, 'Formato de UC inválido', 'UC_INVALIDA')
    return f'UC{match.group(1)}'


def mascarar_documento(doc: str | None) -> str:
    if not doc or not isinstance(doc, str):
        return '***'
    limpo = doc.strip()
    if re.fullmatch(r'\*{3}\.\d{3}\.\d{3}-\*{2}', limpo) or re.fullmatch(
        r'\*{2}\.\d{3}\.\d{3}/\d{4}-\*{2}', limpo
    ):
        return limpo
    if '*' in limpo:
        return '***'
    digitos = re.sub(r'\D', '', limpo)
    if len(digitos) == 11:
        return f'***.{digitos[3:6]}.{digitos[6:9]}-**'
    if len(digitos) == 14:
        return f'**.{digitos[2:5]}.{digitos[5:8]}/{digitos[8:12]}-**'
    return '***'


def subtrair_meses(d: date, meses: int) -> date:
    ano = d.year
    mes = d.month - meses
    while mes <= 0:
        mes += 12
        ano -= 1
    while mes > 12:
        mes -= 12
        ano += 1
    return date(ano, mes, 1)


def formatar_moeda_br(v: Decimal) -> str:
    s = f'{v:,.2f}'
    return f'R$ {s.replace(",", "X").replace(".", ",").replace("X", ".")}'


def formatar_tarifa_br(t: Decimal) -> str:
    s = f'{t:f}'
    if '.' in s:
        int_part, dec_part = s.split('.', 1)
        dec_part = dec_part.rstrip('0')
        if len(dec_part) < 2:
            dec_part = dec_part.ljust(2, '0')
        val_str = f'{int_part},{dec_part}'
    else:
        val_str = f'{s},00'
    return f'R$ {val_str}'


def formatar_pct_br(p: Decimal) -> str:
    return f'{abs(p):.1f}%'.replace('.', ',')


def nome_bandeira(b: str) -> str:
    nomes = {
        'VERDE': 'Verde',
        'AMARELA': 'Amarela',
        'VERMELHA_P1': 'Vermelha P1',
        'VERMELHA_P2': 'Vermelha P2',
    }
    return nomes.get(b.upper(), b)


def explicar_conta(atual: Mapping | None, anterior: Mapping | None) -> ExplicacaoConta:
    if not atual or not atual.get('id_fatura'):
        return ExplicacaoConta(
            situacao='SEM_FATURA',
            frase='A UC ainda não tem fatura emitida.',
            atual=None,
            anterior=None,
            variacao_valor=None,
            variacao_valor_pct=None,
            variacao_consumo_pct=None,
            efeitos=None,
        )

    comp_atual = atual['competencia']
    fat_atual = FaturaComparada(
        competencia=comp_atual,
        id_fatura=atual['id_fatura'],
        volume_faturado_kwh=Decimal(str(atual['volume_faturado_kwh'])),
        valor_total=Decimal(str(atual['valor_total'])),
        tarifa_base=Decimal(str(atual['tarifa_base'])),
        adicional_bandeira=Decimal(str(atual['adicional_bandeira'])),
        bandeira=atual['bandeira'],
        leitura_estimada=(
            atual.get('tipo_leitura') == 'ESTIMADA' or bool(atual.get('leitura_estimada'))
        ),
        troca_medidor=(bool(atual.get('flag_troca_medidor')) or bool(atual.get('troca_medidor'))),
    )

    if not anterior or not anterior.get('id_fatura'):
        comp_ant_esperada = subtrair_meses(comp_atual, 12)
        mes_ano_ant = comp_ant_esperada.strftime('%m/%Y')
        frase = (
            f'Não há fatura de {mes_ano_ant} para comparar: '
            'a UC não tem um ano de histórico de faturamento.'
        )
        if fat_atual.troca_medidor:
            frase += (
                f' Em {comp_atual.strftime("%m/%Y")} houve troca de medidor, '
                'e o consumo do mês foi estimado pela média da UC.'
            )
        elif fat_atual.leitura_estimada:
            frase += f' A leitura de {comp_atual.strftime("%m/%Y")} foi estimada.'

        return ExplicacaoConta(
            situacao='SEM_BASE',
            frase=frase,
            atual=fat_atual,
            anterior=None,
            variacao_valor=None,
            variacao_valor_pct=None,
            variacao_consumo_pct=None,
            efeitos=None,
        )

    comp_anterior = anterior['competencia']
    fat_anterior = FaturaComparada(
        competencia=comp_anterior,
        id_fatura=anterior['id_fatura'],
        volume_faturado_kwh=Decimal(str(anterior['volume_faturado_kwh'])),
        valor_total=Decimal(str(anterior['valor_total'])),
        tarifa_base=Decimal(str(anterior['tarifa_base'])),
        adicional_bandeira=Decimal(str(anterior['adicional_bandeira'])),
        bandeira=anterior['bandeira'],
        leitura_estimada=(
            anterior.get('tipo_leitura') == 'ESTIMADA' or bool(anterior.get('leitura_estimada'))
        ),
        troca_medidor=(
            bool(anterior.get('flag_troca_medidor')) or bool(anterior.get('troca_medidor'))
        ),
    )

    q0 = fat_anterior.volume_faturado_kwh
    r0 = fat_anterior.valor_total
    t0 = q0 * fat_anterior.tarifa_base
    b0 = q0 * fat_anterior.adicional_bandeira

    q1 = fat_atual.volume_faturado_kwh
    r1 = fat_atual.valor_total
    t1 = q1 * fat_atual.tarifa_base
    b1 = q1 * fat_atual.adicional_bandeira

    ef = decompor(q0=q0, r0=r0, t0=t0, b0=b0, q1=q1, r1=r1, t1=t1, b1=b1)
    efeitos = EfeitosConta(
        consumo=ef.volume,
        tarifa=ef.reajuste,
        bandeira=ef.bandeira,
        outros=ef.mix,
    )

    delta_r = r1 - r0
    delta_q = q1 - q0

    variacao_valor = delta_r
    variacao_valor_pct = (
        ((delta_r / r0) * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if r0 != 0 else None
    )
    variacao_consumo_pct = (
        ((delta_q / q0) * 100).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP) if q0 != 0 else None
    )

    pct_consumo_int = (
        ((delta_q / q0) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
        if q0 != 0
        else Decimal(0)
    )
    if pct_consumo_int > 0:
        parte_consumo = f'O consumo faturado subiu {pct_consumo_int}%'
    elif pct_consumo_int < 0:
        parte_consumo = f'O consumo faturado caiu {abs(pct_consumo_int)}%'
    else:
        parte_consumo = 'O consumo faturado ficou estável'

    if delta_r == 0:
        parte_fatura = 'a fatura ficou igual'
    else:
        verbo = 'subiu' if delta_r > 0 else 'caiu'
        str_delta_r = formatar_moeda_br(abs(delta_r))
        pct_r_val = variacao_valor_pct if variacao_valor_pct is not None else Decimal('0.0')
        str_pct_r = formatar_pct_br(pct_r_val)

        candidatos = [
            ('consumo', ef.volume),
            ('bandeira', ef.bandeira),
            ('tarifa', ef.reajuste),
        ]
        compativeis = [
            (nome, val) for nome, val in candidatos if (val > 0 if delta_r > 0 else val < 0)
        ]
        if not compativeis:
            motivo = 'por tributos e outros componentes'
        else:
            melhor_nome, _ = max(compativeis, key=lambda item: abs(item[1]))
            if melhor_nome == 'consumo':
                motivo = 'principalmente pela variação do consumo'
            elif melhor_nome == 'bandeira':
                nome_atual = nome_bandeira(str(fat_atual.bandeira))
                nome_anterior = nome_bandeira(str(fat_anterior.bandeira))
                if nome_atual != nome_anterior:
                    motivo = (
                        f'principalmente por causa da bandeira {nome_atual} (antes {nome_anterior})'
                    )
                else:
                    motivo = f'principalmente por causa da bandeira {nome_atual}'
            else:
                t_ant_str = formatar_tarifa_br(fat_anterior.tarifa_base)
                t_at_str = formatar_tarifa_br(fat_atual.tarifa_base)
                motivo = (
                    'principalmente pelo reajuste da tarifa '
                    f'(de {t_ant_str} para {t_at_str} por kWh)'
                )

        parte_fatura = f'a fatura {verbo} {str_delta_r} ({str_pct_r}) {motivo}'

    frase = f'{parte_consumo}; {parte_fatura}.'

    for fat in (fat_anterior, fat_atual):
        mes_ano = fat.competencia.strftime('%m/%Y')
        if fat.troca_medidor:
            frase += (
                f' Em {mes_ano} houve troca de medidor, '
                'e o consumo do mês foi estimado pela média da UC.'
            )
        elif fat.leitura_estimada:
            frase += f' A leitura de {mes_ano} foi estimada.'

    return ExplicacaoConta(
        situacao='COMPARADA',
        frase=frase,
        atual=fat_atual,
        anterior=fat_anterior,
        variacao_valor=variacao_valor,
        variacao_valor_pct=variacao_valor_pct,
        variacao_consumo_pct=variacao_consumo_pct,
        efeitos=efeitos,
    )


async def obter_visao_uc(db, id_uc_bruto: str) -> VisaoUC:
    id_uc = normalizar_id_uc(id_uc_bruto)
    uc_row = await repo.buscar_dim_uc(db, id_uc)
    if not uc_row:
        raise APIError(404, 'Unidade consumidora não encontrada', 'UC_NAO_ENCONTRADA')

    data_referencia, periodo_fim_carga = await repo.buscar_info_carga(db)
    medidor_row = await repo.buscar_medidor_atual(db, id_uc)
    gd_row = await repo.buscar_gd(db, id_uc)

    cabecalho = Cabecalho(
        titular=uc_row['titular'],
        documento=mascarar_documento(uc_row['documento_mascarado']),
        classe=uc_row['classe'],
        endereco=uc_row['endereco'],
        municipio=uc_row['municipio'],
        bairro=uc_row['bairro'],
        alimentador=uc_row['alimentador'],
        medidor_atual=(
            MedidorAtual(
                id_medidor=medidor_row['id_medidor'],
                tipo_medidor=medidor_row['tipo_medidor'],
                data_instalacao=medidor_row['data_instalacao'],
            )
            if medidor_row
            else None
        ),
        gd=(
            GD(potencia_kw=gd_row['potencia_kw'], data_conexao=gd_row['data_conexao'])
            if gd_row
            else None
        ),
    )

    maior_comp = await repo.buscar_maior_competencia(db, id_uc)
    fim = maior_comp if maior_comp is not None else periodo_fim_carga
    inicio = subtrair_meses(fim, 11)
    inicio_ano_anterior = subtrair_meses(inicio, 12)

    rows_consumo = await repo.listar_consumo_faturamento(db, id_uc, inicio_ano_anterior, fim)
    mapa_consumo = {r['competencia']: r for r in rows_consumo}

    meses = []
    for i in range(12):
        comp_mes = subtrair_meses(inicio, -i)
        comp_ant = subtrair_meses(comp_mes, 12)
        r_at = mapa_consumo.get(comp_mes)
        r_ant = mapa_consumo.get(comp_ant)

        p_at = (
            PontoConsumo(
                competencia=comp_mes,
                consumo_kwh=r_at['consumo_kwh_analitico'],
                leitura_estimada=(r_at['tipo_leitura'] == 'ESTIMADA'),
                troca_medidor=bool(r_at['flag_troca_medidor']),
                consumo_ajustado=(r_at['metodo_consumo'] != 'LEITURA_UTILIZAVEL'),
            )
            if r_at
            else None
        )

        p_ant = (
            PontoConsumo(
                competencia=comp_ant,
                consumo_kwh=r_ant['consumo_kwh_analitico'],
                leitura_estimada=(r_ant['tipo_leitura'] == 'ESTIMADA'),
                troca_medidor=bool(r_ant['flag_troca_medidor']),
                consumo_ajustado=(r_ant['metodo_consumo'] != 'LEITURA_UTILIZAVEL'),
            )
            if r_ant
            else None
        )

        meses.append(MesConsumo(competencia=comp_mes, atual=p_at, anterior=p_ant))

    consumo = Consumo(competencia_inicial=inicio, competencia_final=fim, meses=meses)

    atual_fat = await repo.buscar_ultima_fatura(db, id_uc)
    anterior_fat = None
    if atual_fat:
        comp_ant_esperada = subtrair_meses(atual_fat['competencia'], 12)
        anterior_fat = await repo.buscar_fatura_competencia(db, id_uc, comp_ant_esperada)

    explicacao = explicar_conta(atual_fat, anterior_fat)

    rows_abertas = await repo.listar_faturas_abertas(db, id_uc)
    faturas_abertas = []
    for r in rows_abertas:
        if data_referencia is not None and r['data_vencimento'] is not None:
            atraso = max(0, (data_referencia - r['data_vencimento']).days)
        else:
            atraso = None
        faturas_abertas.append(
            FaturaAberta(
                id_fatura=r['id_fatura'],
                competencia=r['competencia'],
                valor_total=r['valor_total'],
                data_vencimento=r['data_vencimento'],
                bandeira=r['bandeira'],
                dias_atraso=atraso,
            )
        )

    fim_plus_1m = subtrair_meses(fim, -1)
    rows_ocorrencias = await repo.listar_ocorrencias_uc(db, id_uc, inicio, fim_plus_1m)
    ocorrencias = [
        OcorrenciaUC(
            id_ocorrencia=r['id_ocorrencia'],
            data_abertura=r['data_abertura'],
            data_encerramento=r['data_encerramento'],
            duracao_min=Decimal(str(r['duracao_min'])),
            causa=r['causa'],
        )
        for r in rows_ocorrencias
    ]

    alm_stats = await repo.resumo_alimentador(db, uc_row['alimentador'], inicio, fim)
    soma_interrupcoes = int(alm_stats['soma_interrupcoes']) if alm_stats else 0
    soma_chi = Decimal(str(alm_stats['soma_chi'])) if alm_stats else Decimal(0)
    num_ucs = (
        Decimal(str(alm_stats['numero_ucs']))
        if (alm_stats and alm_stats['numero_ucs'])
        else Decimal(0)
    )

    if num_ucs > 0:
        dec = (soma_chi / num_ucs).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    else:
        dec = Decimal('0.00')

    resumo_alm = ResumoAlimentador(
        alimentador=uc_row['alimentador'], ocorrencias=soma_interrupcoes, dec=dec
    )
    interrupcoes = Interrupcoes(ocorrencias=ocorrencias, alimentador=resumo_alm)

    rows_chamados = await repo.listar_chamados(db, id_uc)
    protos = [r['protocolo'] for r in rows_chamados]
    mapa_historico = await repo.listar_historico_chamados(db, protos)

    chamados = []
    for r in rows_chamados:
        hist_rows = mapa_historico.get(r['protocolo'], [])
        historico = [
            ChamadoHistorico(
                sequencia=h['sequencia'],
                data=h['data'],
                descricao=h['descricao'],
            )
            for h in hist_rows
        ]
        nota = int(r['nota']) if (r['nota'] is not None and str(r['nota']).strip() != '') else None
        chamados.append(
            Chamado(
                protocolo=r['protocolo'],
                aberto_em=r['aberto_em'],
                assunto=r['assunto'],
                status=r['status'],
                nota=nota,
                historico=historico,
            )
        )

    rows_inspecoes = await repo.listar_inspecoes(db, id_uc)
    inspecoes = [
        Inspecao(
            id_inspecao=r['id_inspecao'],
            data=r['data'],
            inspetor=r['inspetor'],
            resultado=r['resultado'],
            tipo_irregularidade=r['tipo_irregularidade'],
            kwh_recuperado=r['kwh_recuperado'],
            origem=r['origem'],
        )
        for r in rows_inspecoes
    ]

    ordem_row = await repo.buscar_ordem_ativa(db, id_uc)
    ordem_ativa = Ordem.model_validate(dict(ordem_row)) if ordem_row else None

    return VisaoUC(
        id_uc=id_uc,
        data_referencia=data_referencia,
        cabecalho=cabecalho,
        consumo=consumo,
        faturas_abertas=faturas_abertas,
        interrupcoes=interrupcoes,
        chamados=chamados,
        inspecoes=inspecoes,
        ordem_ativa=ordem_ativa,
        explicacao_conta=explicacao,
    )
