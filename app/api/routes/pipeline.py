"""Pipeline routes.

Endpoints for triggering a pipeline run over a user's uploaded documents
and polling the run's status by run_id. The trigger returns immediately
(202) with a run whose stages are all pending; the actual work runs in a
background task. The frontend polls GET /pipeline/runs/{run_id} to show
which agent is currently running.
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.models.pipeline import Run, RunRequest
from app.pipeline.orchestrator import run_pipeline
from app.services import onboarding_service, pipeline_service

router = APIRouter(prefix="/pipeline", tags=["pipeline"])


@router.post("/runs", response_model=Run, status_code=202)
def trigger_run(payload: RunRequest, background: BackgroundTasks) -> Run:
    """Create a run and kick off the pipeline in the background."""
    if onboarding_service.get_user(str(payload.user_id)) is None:
        raise HTTPException(status_code=404, detail="User not found")

    run = pipeline_service.create_run(str(payload.user_id))
    background.add_task(run_pipeline, str(run.id))
    return run


@router.get("/runs/{run_id}", response_model=Run)
def get_run(run_id: str) -> Run:
    """Return the current status of a run (for polling)."""
    run = pipeline_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run
