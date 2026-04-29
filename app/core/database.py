import os
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

    async def init_schema(self) -> None:
        """
        개발 초기용 DDL.
        """
        await self.execute("""
        CREATE EXTENSION IF NOT EXISTS "pgcrypto";
        """)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name VARCHAR(100),
            role VARCHAR(50) DEFAULT 'USER',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            owner_id UUID REFERENCES users(id) ON DELETE SET NULL,
            name VARCHAR(255) NOT NULL,
            address TEXT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS data_transform (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            building_id UUID REFERENCES buildings(id) ON DELETE CASCADE,
            status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
            scan_file_path TEXT,
            error_message TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await self.execute("""
        CREATE TABLE IF NOT EXISTS graph_data (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            building_id UUID REFERENCES buildings(id) ON DELETE CASCADE,
            data_transform_id UUID REFERENCES data_transform(id) ON DELETE SET NULL,
            graph_json JSONB NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


db = Database()
