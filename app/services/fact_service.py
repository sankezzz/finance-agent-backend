"""Financial-fact service.

Reads/writes point-in-time financial facts (salary, loan outstanding,
investment/FD value, etc.) for a run. The parser inserts rows via
create_facts; the analysis agent reads them back by run_id to build the
Income / Assets / Liabilities picture.
"""

from app.db.supabase_client import get_supabase
from app.models.fact import FinancialFact, FinancialFactCreate

TABLE = "financial_facts"


def create_facts(payloads: list[FinancialFactCreate]) -> list[FinancialFact]:
    """Bulk-insert financial facts and return the stored rows."""
    if not payloads:
        return []
    db = get_supabase()
    rows = [p.model_dump(mode="json") for p in payloads]
    resp = db.table(TABLE).insert(rows).execute()
    return [FinancialFact(**row) for row in resp.data]


def list_facts(run_id: str) -> list[FinancialFact]:
    """Return all financial facts for a run."""
    db = get_supabase()
    resp = db.table(TABLE).select("*").eq("run_id", run_id).execute()
    return [FinancialFact(**row) for row in resp.data]
