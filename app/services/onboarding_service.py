"""Onboarding service.

Handles creating/reading the user profile captured during onboarding
(name, age, monthly income, dependents, existing loans, financial goals).
Talks to the Supabase `users` table via the shared client.
"""

from app.db.supabase_client import get_supabase
from app.models.user import User, UserCreate

TABLE = "users"


def create_user(payload: UserCreate) -> User:
    """Insert a new user row and return the stored profile."""
    db = get_supabase()
    # mode="json" serializes enums -> values and dates -> ISO strings so the
    # nested loan/goal lists land cleanly in jsonb columns.
    row = payload.model_dump(mode="json")
    resp = db.table(TABLE).insert(row).execute()
    return User(**resp.data[0])


def get_user(user_id: str) -> User | None:
    """Fetch a user profile by id, or None if it doesn't exist."""
    db = get_supabase()
    resp = db.table(TABLE).select("*").eq("id", user_id).limit(1).execute()
    if not resp.data:
        return None
    return User(**resp.data[0])
