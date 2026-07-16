"""Transaction service.

Reads/writes ledger transactions for a run. The parser inserts rows via
create_transactions; downstream agents (categorizer, analysis) read them
back by run_id.
"""

from collections import defaultdict

from app.db.supabase_client import get_supabase
from app.models.transaction import Transaction, TransactionCreate

TABLE = "transactions"


class CategoryUpdate:
    """A categorizer result for one transaction (id + the three fields)."""

    __slots__ = ("id", "category", "is_recurring", "is_subscription")

    def __init__(self, id: str, category: str, is_recurring: bool, is_subscription: bool):
        self.id = str(id)
        self.category = category
        self.is_recurring = is_recurring
        self.is_subscription = is_subscription


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


def apply_categorizations(updates: list[CategoryUpdate]) -> None:
    """Persist categorizer results.

    Groups rows that share the same (category, is_recurring, is_subscription)
    so we issue a handful of bulk UPDATE ... WHERE id IN (...) calls instead of
    one per transaction.
    """
    if not updates:
        return
    db = get_supabase()
    groups: dict[tuple[str, bool, bool], list[str]] = defaultdict(list)
    for u in updates:
        groups[(u.category, u.is_recurring, u.is_subscription)].append(u.id)

    for (category, is_recurring, is_subscription), ids in groups.items():
        db.table(TABLE).update(
            {
                "category": category,
                "is_recurring": is_recurring,
                "is_subscription": is_subscription,
            }
        ).in_("id", ids).execute()
