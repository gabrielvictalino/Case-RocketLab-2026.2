import json

from sqlalchemy import text

COLUNAS = (
    'id',
    'conversa_id',
    'usuario_id',
    'pergunta',
    'contexto',
    'consultas',
    'sql_gerado',
    'sql_executado',
    'numero_linhas',
    'resposta',
    'nao_sei',
    'motivo',
    'modelo',
    'tokens_entrada',
    'tokens_saida',
    'latencia_ms',
    'erro',
)
JSON = {'contexto', 'consultas'}


async def registrar(db, registro):
    valores = ','.join(f'CAST(:{c} AS jsonb)' if c in JSON else f':{c}' for c in COLUNAS)
    await db.execute(
        text(f'INSERT INTO operations.agente_auditoria ({",".join(COLUNAS)}) VALUES ({valores})'),
        {c: json.dumps(registro[c]) if c in JSON else registro.get(c) for c in COLUNAS},
    )


async def dono_da_conversa(db, conversa_id):
    return await db.scalar(
        text(
            'SELECT usuario_id FROM operations.agente_auditoria '
            'WHERE conversa_id=:conversa ORDER BY criado_em LIMIT 1'
        ),
        {'conversa': conversa_id},
    )


async def mensagens(db, conversa_id):
    return (
        (
            await db.execute(
                text(
                    'SELECT id AS id_resposta, usuario_id, pergunta, resposta, nao_sei, motivo, '
                    'erro, criado_em FROM operations.agente_auditoria '
                    'WHERE conversa_id=:conversa ORDER BY criado_em, id'
                ),
                {'conversa': conversa_id},
            )
        )
        .mappings()
        .all()
    )


async def obter(db, id_resposta):
    return (
        (
            await db.execute(
                text(
                    'SELECT a.id AS id_resposta, a.conversa_id, a.usuario_id, u.login AS usuario, '
                    'a.pergunta, a.contexto, a.consultas, a.sql_gerado, a.sql_executado, '
                    'a.numero_linhas, a.resposta, a.nao_sei, a.motivo, a.modelo, '
                    'a.tokens_entrada, a.tokens_saida, a.latencia_ms, a.erro, a.criado_em '
                    'FROM operations.agente_auditoria a '
                    'JOIN operations.usuarios u ON u.id = a.usuario_id WHERE a.id=:id'
                ),
                {'id': id_resposta},
            )
        )
        .mappings()
        .first()
    )
