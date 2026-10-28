"""Amostra determinística. Todos os valores são inventados; nenhuma fórmula oficial."""

import csv
import hashlib
import json
from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def gerar(out=OUT):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    specs = {
        p.stem: yaml.safe_load(p.read_text()) for p in sorted((ROOT / 'tabelas').glob('*.yaml'))
    }
    data = {name: [] for name in specs}
    municipios = ['Recife', 'Jaboatão', 'Olinda']
    classes = ['Residencial', 'Comercial', 'Industrial', 'Rural', 'Poder Público']
    feeders = [
        f'ALM-{sigla}-{i + 1:03}'
        for i, sigla in enumerate(['REC', 'REC', 'JAB', 'JAB', 'OLI', 'OLI'])
    ]
    counts = defaultdict(int)
    for i in range(300):
        feeder = i % 5 if i < 299 else 5
        counts[feeder] += 1
        uc = f'UC{100000 + i}'
        data['dim_uc'].append(
            dict(
                id_uc=uc,
                titular=f'Titular sintético {i:03}',
                documento_mascarado='***.000.000-**',
                endereco=f'Rua fictícia, {i}',
                municipio=municipios[feeder // 2],
                bairro=f'Bairro sintético {feeder + 1}',
                classe=classes[(i // 5) % 5],
                alimentador=feeders[feeder],
                flag_gd=i == 0,
                flag_irregularidade_confirmada=i == 1,
            )
        )
        data['medidores_historico'].append(
            dict(
                id_medidor=f'MD{100000 + i}',
                id_uc=uc,
                data_instalacao='2022-07-01',
                data_retirada='2025-09-01' if i == 1 else None,
                tipo_medidor='SINTETICO',
            )
        )
    data['medidores_historico'].append(
        dict(
            id_medidor='MD999999',
            id_uc='UC100001',
            data_instalacao='2025-09-01',
            data_retirada=None,
            tipo_medidor='SINTETICO',
        )
    )
    data['gd_uc'].append(dict(id_uc='UC100000', potencia_kw=5, data_conexao='2025-01-01'))
    for i, feeder in enumerate(feeders):
        data['dim_alimentador'].append(
            dict(alimentador=feeder, municipio=municipios[i // 2], numero_ucs=counts[i])
        )

    aggregated = {}
    for offset in range(48):
        year, month = divmod(2022 * 12 + 6 + offset, 12)
        competencia = date(year, month + 1, 1).isoformat()
        for i, uc in enumerate(data['dim_uc']):
            # UC nova sem comparação anual, valores nulos e fatura em aberto.
            if i == 298 and offset < 36:
                continue
            troca = i == 1 and competencia == '2025-09-01'
            consumo = Decimal(100 + i % 30 + offset % 12)
            grupo = 'DEMAIS'
            if i == 0 and competencia >= '2025-01-01':
                grupo, consumo = 'GD', Decimal('40')
            elif i == 1 and competencia >= '2025-08-01':
                grupo, consumo = 'IRREGULARIDADE_CONFIRMADA', Decimal('60')
            tarifa = Decimal('0.70') if offset < 24 else Decimal('0.80')
            bandeira = Decimal('0.10') if offset == 36 else Decimal('0')
            receita = (consumo * (tarifa + bandeira)).quantize(Decimal('0.01'))
            paga = not (i == 3 and offset >= 45)
            row = dict(
                id_uc=uc['id_uc'],
                competencia=competencia,
                consumo_kwh_original=-500 if troca else consumo,
                consumo_kwh_analitico=consumo,
                metodo_consumo='SINTETICO_TROCA' if troca else 'SINTETICO',
                tipo_leitura='ESTIMADA' if i == 2 and offset == 47 else 'REAL',
                flag_troca_medidor=troca,
                id_fatura=f'FT{i:06}{offset:03}',
                volume_faturado_kwh=consumo,
                valor_total=receita,
                valor_arrecadado=receita if paga else Decimal(0),
                tarifa_base=tarifa,
                adicional_bandeira=bandeira,
                bandeira='AMARELA_SINTETICA' if bandeira else 'VERDE',
                status_pagamento='PAGA' if paga else 'ABERTA',
                grupo_uc=grupo,
            )
            data['uc_consumo_faturamento_mensal'].append(row)
            key = (competencia, uc['municipio'], uc['bairro'], uc['classe'], grupo)
            if key not in aggregated:
                aggregated[key] = dict(
                    zip(['competencia', 'municipio', 'bairro', 'classe', 'grupo_uc'], key)
                )
                for field in (
                    'volume_faturado_kwh',
                    'receita',
                    'receita_arrecadada',
                    'componente_tarifa_reais',
                    'componente_bandeira_reais',
                ):
                    aggregated[key][field] = Decimal(0)
            agg = aggregated[key]
            agg['volume_faturado_kwh'] += consumo
            agg['receita'] += receita
            agg['receita_arrecadada'] += row['valor_arrecadado']
            agg['componente_tarifa_reais'] += consumo * tarifa
            agg['componente_bandeira_reais'] += consumo * bandeira
        for i, feeder in enumerate(feeders):
            atipico = offset == 36 and i == 0
            minutos = 12000 if atipico else (240 if i == 5 else 60)
            target = next(u['id_uc'] for u in data['dim_uc'] if u['alimentador'] == feeder)
            inicio = competencia[:7] + '-02T00:00:00'
            fim = competencia[:7] + (
                '-10T08:00:00' if atipico else ('-02T04:00:00' if i == 5 else '-02T01:00:00')
            )
            data['ocorrencias_uc'].append(
                dict(
                    id_ocorrencia=f'OC{offset:06}{i:02}',
                    id_uc=target,
                    alimentador=feeder,
                    data_abertura=inicio,
                    data_encerramento=fim,
                    duracao_min=minutos,
                    duracao_efetiva_min=minutos,
                    causa='SINTETICA',
                    flag_sobreposicao=False,
                )
            )
            chi = Decimal(minutos) / 60
            data['continuidade_alimentador_mensal'].append(
                dict(
                    alimentador=feeder,
                    competencia=competencia,
                    numero_ucs=counts[i],
                    chi_horas=chi,
                    interrupcoes=1,
                    dec=(chi / counts[i]).quantize(Decimal('0.01')),
                    fec=(Decimal(1) / counts[i]).quantize(Decimal('0.01')),
                    causa='SINTETICA',
                    flag_evento_atipico=atipico,
                )
            )
    data['receita_volume_mensal'] = [aggregated[k] for k in sorted(aggregated)]
    for i in range(2):
        data['atendimentos'].append(
            dict(
                protocolo=f'AT{i:09}',
                id_uc=f'UC{100000 + i}',
                aberto_em='2026-06-01T10:00:00',
                assunto='Dúvida sintética',
                status='ENCERRADO',
                nota=None if i else 10,
            )
        )
        data['atendimentos_historico'].append(
            dict(
                protocolo=f'AT{i:09}',
                sequencia=1,
                data='2026-06-01T11:00:00',
                descricao='Tratativa sintética',
            )
        )
        data['inspecoes_historicas'].append(
            dict(
                id_inspecao=f'IN{i:07}',
                id_uc=f'UC{100001 + i}',
                data='2025-08-10',
                inspetor='INSP-001',
                resultado='SEM IRREGULARIDADE' if i else 'IRREGULARIDADE CONFIRMADA',
                tipo_irregularidade=None if i else 'DESVIO DIRETO',
                kwh_recuperado=0 if i else 100,
            )
        )
    for i in range(12):
        data['fila_inspecao'].append(
            dict(
                id_uc=f'UC{100000 + i}',
                score=Decimal(100 - i),
                motivos=['Sinal exclusivamente sintético'],
                energia_recuperar_kwh=100 + i,
                energia_recuperar_reais=80 + i,
            )
        )

    manifest = dict(
        batch_id='amostra-sintetica-v1',
        contract_version=(ROOT / 'VERSION').read_text().strip(),
        synthetic=True,
        period={'start': '2022-07', 'end': '2026-06'},
        tables={},
    )
    for name, spec in specs.items():
        filename = out / f'{name}.csv'
        with filename.open('w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(spec['columns']), lineterminator='\n')
            writer.writeheader()
            for row in data[name]:
                writer.writerow(
                    {
                        k: ''
                        if v is None
                        else json.dumps(v, ensure_ascii=False)
                        if isinstance(v, (list, bool))
                        else v
                        for k, v in row.items()
                    }
                )
        totals = {
            c: str(sum((Decimal(str(r[c])) for r in data[name]), Decimal(0)))
            for c in spec.get('control_totals', [])
        }
        manifest['tables'][name] = dict(
            file=f'{name}.csv',
            rows=len(data[name]),
            sha256=hashlib.sha256(filename.read_bytes()).hexdigest(),
            totals=totals,
        )
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    gerar()
