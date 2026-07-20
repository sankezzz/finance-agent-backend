"""Parser LLM extraction contract.

The shape the parser asks the LLM to return (via `instructor`, JSON mode).
One response can carry both ledger line-items (`transactions`) and
point-in-time figures (`facts`); the per-document-type prompt decides which
to fill. The agent then maps these into TransactionCreate / FinancialFactCreate
rows (adding run_id, user_id, document_id).

Small models are loose with strict schemas (null vs [], string vs date, null
for required fields), so every field has a lenient `before` validator that
normalizes junk rather than failing — instructor's retry loop is the backstop.
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.models.fact import FactKind
from app.models.transaction import TransactionDirection

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d %b %Y", "%d %B %Y")


class ExtractedTransaction(BaseModel):
    txn_date: date | None = None
    description: str = Field(default="Unknown", min_length=1)
    amount: float = Field(default=0.0, ge=0)
    direction: TransactionDirection = TransactionDirection.debit
    merchant: str | None = None
    currency: str = "INR"

    @field_validator("txn_date", mode="before")
    @classmethod
    def _parse_date(cls, v):
        if v is None or v == "" or isinstance(v, date):
            return v or None
        text = str(v).strip()
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @field_validator("description", mode="before")
    @classmethod
    def _clean_description(cls, v):
        return "Unknown" if v is None or str(v).strip() == "" else str(v)

    @field_validator("amount", mode="before")
    @classmethod
    def _clean_amount(cls, v):
        return abs(v) if isinstance(v, (int, float)) else 0.0

    @field_validator("direction", mode="before")
    @classmethod
    def _clean_direction(cls, v):
        # Return an enum *instance* (not the raw 'credit' string) so validation
        # passes under both Groq's lenient JSON mode and Gemini's strict
        # structured-output mode. Junk falls back to debit.
        if isinstance(v, TransactionDirection):
            return v
        try:
            return TransactionDirection(str(v).strip().lower())
        except (ValueError, AttributeError):
            return TransactionDirection.debit

    @field_validator("currency", mode="before")
    @classmethod
    def _clean_currency(cls, v):
        return str(v) if v else "INR"


class ExtractedFact(BaseModel):
    kind: FactKind
    subtype: str = Field(default="other", min_length=1)
    label: str | None = None
    amount: float = Field(default=0.0)
    currency: str = "INR"
    meta: dict[str, object] = Field(default_factory=dict)

    @field_validator("kind", mode="before")
    @classmethod
    def _clean_kind(cls, v):
        # Coerce to a FactKind instance for Gemini's strict structured-output
        # mode. `kind` is required with no sane default, so an invalid value
        # raises here → instructor retries rather than mislabelling the fact.
        if isinstance(v, FactKind):
            return v
        return FactKind(str(v).strip().lower())

    @field_validator("subtype", mode="before")
    @classmethod
    def _clean_subtype(cls, v):
        return "other" if v is None or str(v).strip() == "" else str(v)

    @field_validator("amount", mode="before")
    @classmethod
    def _clean_amount(cls, v):
        return float(v) if isinstance(v, (int, float)) else 0.0

    @field_validator("currency", mode="before")
    @classmethod
    def _clean_currency(cls, v):
        return str(v) if v else "INR"

    @field_validator("meta", mode="before")
    @classmethod
    def _clean_meta(cls, v):
        return v if isinstance(v, dict) else {}


class ParsedDocument(BaseModel):
    """What the LLM returns for a single document."""

    summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    transactions: list[ExtractedTransaction] = Field(default_factory=list)
    facts: list[ExtractedFact] = Field(default_factory=list)

    @field_validator("warnings", "transactions", "facts", mode="before")
    @classmethod
    def _null_to_empty(cls, v):
        return [] if v is None else v
