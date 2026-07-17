"""FastAPI application entrypoint.

Creates the FastAPI app instance, exposes a health check, registers the
feature routers, and runs a self keep-alive loop so Render's free instance
doesn't sleep.
"""

import asyncio
import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import chat, dashboard, documents, onboarding, pipeline
from app.config import get_settings

# Self keep-alive: Render's free instance sleeps after ~15 min with no inbound
# traffic. We ping our own PUBLIC url every 10 min so the idle timer never
# elapses. It must be the public url (RENDER_EXTERNAL_URL, injected by Render) —
# a localhost ping doesn't go through Render's router and wouldn't count.
_KEEPALIVE_INTERVAL_S = 600


async def _keepalive_loop(health_url: str) -> None:
    async with httpx.AsyncClient(timeout=30) as client:
        while True:
            await asyncio.sleep(_KEEPALIVE_INTERVAL_S)
            try:
                await client.get(health_url)
            except Exception:  # noqa: BLE001 — a failed ping must never crash the loop
                pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # RENDER_EXTERNAL_URL is set automatically on Render; KEEPALIVE_URL lets you
    # override for other hosts. Absent locally → no self-ping in dev.
    base = os.environ.get("KEEPALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")
    task = None
    if base:
        health_url = f"{base.rstrip('/')}/health"
        task = asyncio.create_task(_keepalive_loop(health_url))
        print(f"[keepalive] self-ping enabled -> {health_url} every {_KEEPALIVE_INTERVAL_S}s")
    try:
        yield
    finally:
        if task:
            task.cancel()


app = FastAPI(title="Personal Finance Copilot", lifespan=lifespan)

# CORS — lets the frontend (e.g. the Next.js dev server) call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins_list,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Routers ---------------------------------------------------------------
app.include_router(onboarding.router)
app.include_router(documents.router)
app.include_router(pipeline.router)
app.include_router(dashboard.router)
app.include_router(chat.router)

# Registered as each feature lands:
# from app.api.routes import profile
# app.include_router(profile.router)
