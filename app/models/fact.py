"""Financial fact schemas.

A financial fact is a point-in-time figure (NOT a ledger line-item)
extracted from salary, loan, or investment statements: salary amount,
loan outstanding, investment/FD value, credit-card outstanding, etc.
Facts feed the Income / Assets / Liabilities sections of the profile.
Scoped to a run_id like transactions.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class FactKind(str, Enum):
    income = "income"
    expense = "expense"
    asset = "asset"
    liability = "liability"


class FinancialFactCreate(BaseModel):
    """Payload the parser agent writes to the DB."""

    run_id: UUID
    user_id: UUID
    document_id: UUID | None = None
    kind: FactKind
    # Free-form sub-classification, e.g. salary, home_loan, mutual_fund, fd,
    # cc_outstanding. Kept as text so new statement types don't need a migration.
    subtype: str = Field(min_length=1)
    label: str | None = None
    amount: float
    currency: str = Field(default="INR", min_length=3, max_length=8)
    metadata: dict[str, object] = Field(default_factory=dict)


class FinancialFact(FinancialFactCreate):
    """A stored financial-fact row."""

    id: UUID
    created_at: datetime
