import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.data_transform import router as data_transform_router
from app.api.emergency import router as emergency_router
from app.api.facility import router as facility_router
from app.api.geo import router as geo_router
from app.api.viewer import router as viewer_router
from app.api.dev import (
    data_transform_router as dev_data_transform_router,
    upload_test_router as dev_upload_test_router,
    users_router as dev_users_router,
)
from app.core.database import db


load_dotenv()


def _dev_routes_enabled() -> bool:
    return os.getenv("ENABLE_DEV_ROUTES", "true").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _cors_origins() -> list[str]:
    raw_origins = os.getenv("CORS_ORIGINS")
    if raw_origins:
        return [
            origin.strip().rstrip("/")
            for origin in raw_origins.split(",")
            if origin.strip()
        ]

    origins = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }
    frontend_origin = os.getenv("FRONTEND_ORIGIN")
    if frontend_origin and frontend_origin.strip():
        origins.add(frontend_origin.strip().rstrip("/"))

    return sorted(origins)


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

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(data_transform_router)
app.include_router(emergency_router)
app.include_router(facility_router)
app.include_router(geo_router)
app.include_router(viewer_router)

if _dev_routes_enabled():
    app.include_router(dev_data_transform_router)
    app.include_router(dev_upload_test_router)
    app.include_router(dev_users_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
