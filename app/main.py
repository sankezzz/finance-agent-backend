"""FastAPI application entrypoint.

Creates the FastAPI app instance and exposes a health check endpoint.
Feature routers (onboarding, documents, pipeline, dashboard, profile, chat)
are registered here once they exist.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import dashboard, documents, onboarding, pipeline
from app.config import get_settings

app = FastAPI(title="Personal Finance Copilot")

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

# Registered as each feature lands:
# from app.api.routes import profile, chat
# app.include_router(profile.router)
# app.include_router(chat.router)
