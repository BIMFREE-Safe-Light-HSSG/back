import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI

from app.api.auth import router as auth_router
from app.api.data_transform import router as data_transform_router
from app.api.dev import (
    upload_test_router as dev_upload_test_router,
    users_router as dev_users_router,
)
from app.core.database import db


load_dotenv()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await db.connect()
    await db.init_schema()

    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(
    title=os.getenv("APP_NAME", "BIMFree Backend"),
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(data_transform_router)

# dev 전용, 해당 기능 개발 완료 시 삭제
app.include_router(dev_upload_test_router)
app.include_router(dev_users_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
