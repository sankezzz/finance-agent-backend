"""Normalized transaction schemas.

A transaction is one ledger line-item extracted from a bank or credit-card
statement (date, amount, description, direction). It is scoped to a run_id.
`category` and the recurring/subscription flags are added later by the
categorization agent, so they live only on the stored `Transaction`.
"""

from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionDirection(str, Enum):
    credit = "credit"  # money in
    debit = "debit"    # money out


class TransactionCreate(BaseModel):
    """Payload the parser agent writes to the DB."""

    run_id: UUID
    user_id: UUID
    document_id: UUID | None = None
    txn_date: date | None = None
    description: str = Field(min_length=1)
    amount: float = Field(ge=0)
    direction: TransactionDirection
    currency: str = Field(default="INR", min_length=3, max_length=8)
    merchant: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class Transaction(TransactionCreate):
    """A stored transaction row (adds fields set after insert/categorization)."""

    id: UUID
    category: str | None = None
    is_recurring: bool = False
    is_subscription: bool = False
    created_at: datetime
