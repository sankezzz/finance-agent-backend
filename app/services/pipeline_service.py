"""Pipeline run persistence.

Runs-table CRUD for the pipeline: create a run (with all stages pending),
read it back for polling, and update overall/per-stage status as the
orchestrator advances. Keeps DB access in the service layer; the
orchestrator sequences agents and calls these helpers.
"""

from datetime import datetime, timezone

from app.db.supabase_client import get_supabase
from app.models.pipeline import Run, RunStatus, StageState, StageStatus, initial_stages
from app.pipeline.stages import Stage

TABLE = "runs"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stages_json(stages: list[StageState]) -> list[dict]:
    return [s.model_dump(mode="json") for s in stages]


def create_run(user_id: str) -> Run:
    """Create a run row with every stage marked pending."""
    db = get_supabase()
    row = {
        "user_id": user_id,
        "status": RunStatus.pending.value,
        "stages": _stages_json(initial_stages()),
    }
    resp = db.table(TABLE).insert(row).execute()
    return Run(**resp.data[0])


def get_run(run_id: str) -> Run | None:
    """Fetch a run by id, or None if it doesn't exist."""
    db = get_supabase()
    resp = db.table(TABLE).select("*").eq("id", run_id).limit(1).execute()
    if not resp.data:
        return None
    return Run(**resp.data[0])


def get_latest_run(user_id: str, status: str | None = None) -> Run | None:
    """Return a user's most recent run, optionally filtered by status."""
    db = get_supabase()
    query = db.table(TABLE).select("*").eq("user_id", user_id)
    if status is not None:
        query = query.eq("status", status)
    resp = query.order("created_at", desc=True).limit(1).execute()
    if not resp.data:
        return None
    return Run(**resp.data[0])


def _save(run: Run) -> Run:
    db = get_supabase()
    payload = {
        "status": run.status.value,
        "current_stage": run.current_stage.value if run.current_stage else None,
        "stages": _stages_json(run.stages),
        "error": run.error,
        "updated_at": _now(),
    }
    resp = db.table(TABLE).update(payload).eq("id", str(run.id)).execute()
    return Run(**resp.data[0])


def mark_running(run_id: str) -> Run:
    run = get_run(run_id)
    run.status = RunStatus.running
    return _save(run)


def mark_done(run_id: str) -> Run:
    run = get_run(run_id)
    run.status = RunStatus.done
    run.current_stage = None
    return _save(run)


def mark_failed(run_id: str, error: str) -> Run:
    run = get_run(run_id)
    run.status = RunStatus.failed
    run.error = error
    return _save(run)


def set_stage(
    run_id: str,
    stage: Stage,
    status: StageStatus,
    error: str | None = None,
) -> Run:
    """Update one stage's status (and the run's current_stage when running)."""
    run = get_run(run_id)
    for state in run.stages:
        if state.stage == stage:
            state.status = status
            state.error = error
            break
    if status == StageStatus.running:
        run.current_stage = stage
    return _save(run)
