"""Supabase client factory.

Provides a single configured supabase-py client for the app to use
for all reads/writes. No SQLAlchemy, no ORM — direct table access via
the Supabase SDK.

The client is built with the SECRET key, so it bypasses row-level
security and must only ever be used from server-side code.
"""

from functools import lru_cache

from supabase import Client, create_client

from app.config import get_settings


@lru_cache
def get_supabase() -> Client:
    """Return the shared Supabase client (created once, then cached)."""
    settings = get_settings()
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
