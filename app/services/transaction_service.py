"""Transaction service.

Reads/writes ledger transactions for a run. The parser inserts rows via
create_transactions; downstream agents (categorizer, analysis) read them
back by run_id.
"""

from app.db.supabase_client import get_supabase
from app.models.transaction import Transaction, TransactionCreate

TABLE = "transactions"


def create_transactions(payloads: list[TransactionCreate]) -> list[Transaction]:
    """Bulk-insert normalized transactions and return the stored rows."""
    if not payloads:
        return []
    db = get_supabase()
    rows = [p.model_dump(mode="json") for p in payloads]
    resp = db.table(TABLE).insert(rows).execute()
    return [Transaction(**row) for row in resp.data]


def list_transactions(run_id: str) -> list[Transaction]:
    """Return all transactions for a run, oldest first."""
    db = get_supabase()
    resp = (
        db.table(TABLE)
        .select("*")
        .eq("run_id", run_id)
        .order("txn_date")
        .execute()
    )
    return [Transaction(**row) for row in resp.data]
