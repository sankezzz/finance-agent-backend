"""Recommendation service.

Persists and serves the recommendation set for a run (summary + prioritized
items). One row per run — regenerating upserts on run_id.
"""

from app.db.supabase_client import get_supabase
from app.models.recommendation import RecommendationSet, StoredRecommendations

TABLE = "recommendations"


def _to_stored(row: dict) -> StoredRecommendations:
    return StoredRecommendations(
        id=row["id"],
        run_id=row["run_id"],
        user_id=row["user_id"],
        created_at=row["created_at"],
        summary=row["summary"],
        recommendations=row["items"],
    )


def save(run_id: str, user_id: str, rec_set: RecommendationSet) -> StoredRecommendations:
    """Insert (or overwrite) the recommendation set for a run."""
    db = get_supabase()
    row = {
        "run_id": str(run_id),
        "user_id": str(user_id),
        "summary": rec_set.summary,
        "items": [r.model_dump(mode="json") for r in rec_set.recommendations],
    }
    resp = db.table(TABLE).upsert(row, on_conflict="run_id").execute()
    return _to_stored(resp.data[0])


def get(run_id: str) -> StoredRecommendations | None:
    """Return the recommendation set for a run, or None if not generated yet."""
    db = get_supabase()
    resp = db.table(TABLE).select("*").eq("run_id", run_id).limit(1).execute()
    if not resp.data:
        return None
    return _to_stored(resp.data[0])
