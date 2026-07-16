"""Financial service.

Persists and serves the analysis snapshot (the computed Metrics) for a run.
One snapshot per run — re-analysing upserts on run_id.
"""

from app.db.supabase_client import get_supabase
from app.models.financial import Metrics, Snapshot

TABLE = "financial_snapshots"


def save_snapshot(run_id: str, user_id: str, metrics: Metrics) -> Snapshot:
    """Insert (or overwrite) the snapshot for a run and return it."""
    db = get_supabase()
    row = metrics.model_dump(mode="json")
    row["run_id"] = str(run_id)
    row["user_id"] = str(user_id)
    resp = db.table(TABLE).upsert(row, on_conflict="run_id").execute()
    return Snapshot(**resp.data[0])


def get_snapshot(run_id: str) -> Snapshot | None:
    """Return the snapshot for a run, or None if not computed yet."""
    db = get_supabase()
    resp = db.table(TABLE).select("*").eq("run_id", run_id).limit(1).execute()
    if not resp.data:
        return None
    return Snapshot(**resp.data[0])
