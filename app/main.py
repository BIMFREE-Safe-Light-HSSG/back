from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.database import db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI 서버 시작/종료 시 실행되는 lifecycle 함수.

    서버 시작:
    - PostgreSQL connection pool 생성
    - 개발용 DDL 실행

    서버 종료:
    - PostgreSQL connection pool 종료
    """
    await db.connect()
    await db.init_schema()

    yield

    await db.disconnect()


app = FastAPI(
    title="Fire Digital Twin Backend",
    description="Digital Twin based Facility Management and Fire Response Platform API",
    version="0.1.0",
    lifespan=lifespan,
)


# Frontend 연동을 위한 CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {
        "message": "Fire Digital Twin Backend is running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "ok"
    }


@app.get("/db-test")
async def db_test():
    result = await db.fetch_one(
        """
        SELECT NOW() AS current_time;
        """
    )

    return {
        "status": "db connected",
        "result": result,
    }