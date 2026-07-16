"""Parser LLM extraction contract.

The shape the parser asks the LLM to return (via `instructor`). One
response can carry both ledger line-items (`transactions`) and
point-in-time figures (`facts`); the per-document-type prompt decides
which to fill. The agent then maps these into TransactionCreate /
FinancialFactCreate rows (adding run_id, user_id, document_id).
"""

from datetime import date

from pydantic import BaseModel, Field

from app.models.fact import FactKind
from app.models.transaction import TransactionDirection


class ExtractedTransaction(BaseModel):
    txn_date: date | None = None
    description: str = Field(min_length=1)
    amount: float = Field(ge=0)
    direction: TransactionDirection
    merchant: str | None = None
    currency: str = "INR"


class ExtractedFact(BaseModel):
    kind: FactKind
    subtype: str = Field(min_length=1)
    label: str | None = None
    amount: float
    currency: str = "INR"
    meta: dict[str, object] = Field(default_factory=dict)


class ParsedDocument(BaseModel):
    """What the LLM returns for a single document."""

    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    transactions: list[ExtractedTransaction] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)
