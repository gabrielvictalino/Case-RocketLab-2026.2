from sqlalchemy import text


async def por_login(db, login):
    return (
        (
            await db.execute(
                text('SELECT * FROM operations.usuarios WHERE login=:login AND ativo'),
                {'login': login},
            )
        )
        .mappings()
        .first()
    )
