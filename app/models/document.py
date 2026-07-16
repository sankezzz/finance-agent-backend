"""Uploaded document schemas.

Represents an uploaded financial document (bank statement, credit card
statement, salary slip, investment statement, loan statement), its
declared type, file metadata, storage location, and processing status.
The raw file lives in Supabase Storage; this row is the DB record of it.
"""

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel


class DocumentType(str, Enum):
    bank_statement = "bank_statement"
    credit_card_statement = "credit_card_statement"
    salary_slip = "salary_slip"
    investment_statement = "investment_statement"
    loan_statement = "loan_statement"


class DocumentStatus(str, Enum):
    uploaded = "uploaded"      # stored, not yet processed
    processing = "processing"  # picked up by a pipeline run
    parsed = "parsed"          # parser extracted records
    failed = "failed"          # processing errored


class Document(BaseModel):
    """A stored document record as returned by the API."""

    id: UUID
    user_id: UUID
    doc_type: DocumentType
    filename: str
    storage_path: str
    content_type: str | None = None
    size_bytes: int | None = None
    status: DocumentStatus
    created_at: datetime
