import asyncpg

from app.core.config import settings


async def check_database_connection() -> bool:
    if not settings.database_url:
        return False

    connection = await asyncpg.connect(settings.database_url)
    try:
        return await connection.fetchval("select 1") == 1
    finally:
        await connection.close()
