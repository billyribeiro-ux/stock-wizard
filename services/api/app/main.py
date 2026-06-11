"""FastAPI application factory for the Stock Wizard engine API."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import engine
from .routers import exports, health, results, scanners, scans, vendors


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Stock Wizard API",
        version="0.1.0",
        description="Scanner, backtester and signal engine API.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:4173", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(scanners.router)
    app.include_router(scans.router)
    app.include_router(results.router)
    app.include_router(vendors.router)
    app.include_router(exports.router)
    return app


app = create_app()
