"""FastAPI application entrypoint.

Creates the FastAPI app instance and exposes a health check endpoint.
Feature routers (onboarding, documents, pipeline, dashboard, profile, chat)
are registered here once they exist.
"""

from fastapi import FastAPI

from app.api.routes import onboarding

app = FastAPI(title="Personal Finance Copilot")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# --- Routers ---------------------------------------------------------------
app.include_router(onboarding.router)

# Registered as each feature lands:
# from app.api.routes import documents, pipeline, dashboard, profile, chat
# app.include_router(documents.router)
# app.include_router(pipeline.router)
# app.include_router(dashboard.router)
# app.include_router(profile.router)
# app.include_router(chat.router)
