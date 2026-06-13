import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.buildings import router as buildings_router
from app.api.data_transform import router as data_transform_router
from app.api.facility import router as facility_router
from app.api.fire_risk_assessments import router as fire_risk_assessments_router
from app.api.model_callbacks import router as model_callbacks_router
from app.core.database import db
from app.core.logging import configure_logging


load_dotenv()
configure_logging()


def _dev_routes_enabled() -> bool:
    return os.getenv("ENABLE_DEV_ROUTES", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _cors_origins() -> list[str]:
    origins = {
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    }

    raw_origins = os.getenv("CORS_ORIGINS")
    if raw_origins:
        origins.update(
            origin.strip().rstrip("/")
            for origin in raw_origins.split(",")
            if origin.strip()
        )

    frontend_origin = os.getenv("FRONTEND_ORIGIN")
    if frontend_origin and frontend_origin.strip():
        origins.add(frontend_origin.strip().rstrip("/"))

    return sorted(origins)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    await db.connect()

    try:
        yield
    finally:
        await db.disconnect()


app = FastAPI(
    title=os.getenv("APP_NAME", "SuperSafeTwin Backend"),
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
app.include_router(buildings_router)
app.include_router(data_transform_router)
app.include_router(facility_router)
app.include_router(fire_risk_assessments_router)
app.include_router(model_callbacks_router)

if _dev_routes_enabled():
    from dev.api import routers as dev_routers

    for dev_router in dev_routers:
        app.include_router(dev_router)


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
