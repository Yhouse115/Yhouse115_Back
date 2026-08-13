import asyncio
import os
from typing import AsyncGenerator
import asyncpg
from app.core.config import settings

_pool: asyncpg.Pool = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if (
        _pool is None
        or getattr(_pool, "_closed", False)
        or (_pool._loop and _pool._loop.is_closed())
        or (_pool._loop and current_loop and _pool._loop is not current_loop)
    ):
        db_url = os.getenv("DATABASE_URL", settings.database_url or "postgresql://whyhouse:whyhouse@localhost:5432/whyhouse")
        if "@database:5432" in db_url:
            db_url = db_url.replace("@database:5432", "@localhost:5432")
        _pool = await asyncpg.create_pool(
            db_url,
            min_size=1,
            max_size=10,
            statement_cache_size=0 if "supabase" in db_url else 100
        )
    return _pool


async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn


async def check_database_connection() -> bool:
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT 1;")
            return val == 1
    except Exception:
        return False
