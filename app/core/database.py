import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg
from dotenv import load_dotenv


load_dotenv()


class Database:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL")
        self.pool: asyncpg.Pool | None = None

        if not self.database_url:
            raise ValueError("DATABASE_URL is not set in .env")

    async def connect(self) -> None:
        """
        PostgreSQL connection pool 생성
        """
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                dsn=self._asyncpg_dsn(),
                min_size=1,
                max_size=10,
            )

    async def disconnect(self) -> None:
        """
        PostgreSQL connection pool 종료
        """
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def _get_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("Database pool is not initialized. Call connect() first.")
        return self.pool

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[asyncpg.Connection]:
        pool = self._get_pool()

        async with pool.acquire() as conn:
            yield conn

    def _asyncpg_dsn(self) -> str:
        if self.database_url.startswith("postgresql+asyncpg://"):
            return self.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

        return self.database_url

    async def execute(self, query: str, *args: Any) -> str:
        """
        INSERT, UPDATE, DELETE, DDL 등에 사용.
        반환값 예:
        - 'CREATE TABLE'
        - 'INSERT 0 1'
        - 'UPDATE 1'
        """
        pool = self._get_pool()

        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch_one(self, query: str, *args: Any) -> dict[str, Any] | None:
        """
        SELECT 결과 1개 조회
        """
        pool = self._get_pool()

        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    async def fetch_all(self, query: str, *args: Any) -> list[dict[str, Any]]:
        """
        SELECT 결과 여러 개 조회
        """
        pool = self._get_pool()

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    async def executemany(self, query: str, args_list: list[tuple[Any, ...]]) -> None:
        """
        여러 INSERT/UPDATE를 한 번에 실행
        """
        pool = self._get_pool()

        async with pool.acquire() as conn:
            await conn.executemany(query, args_list)



db = Database()
