"""Document service.

Handles receiving an uploaded document: stores the raw file in a private
Supabase Storage bucket, records a `documents` row (tied to user_id) with
its type/metadata/status, and lists a user's uploaded documents. The
pipeline later reads the raw file back from storage by `storage_path`.
"""

import uuid

from app.db.supabase_client import get_supabase
from app.models.document import Document, DocumentStatus, DocumentType

TABLE = "documents"
BUCKET = "documents"


def create_document(
    *,
    user_id: str,
    doc_type: DocumentType,
    filename: str,
    content_type: str | None,
    content: bytes,
) -> Document:
    """Upload the file to storage and insert its documents row."""
    db = get_supabase()

    # Unique per-document path so re-uploads never collide.
    doc_id = str(uuid.uuid4())
    storage_path = f"{user_id}/{doc_id}/{filename}"

    db.storage.from_(BUCKET).upload(
        storage_path,
        content,
        {"content-type": content_type or "application/octet-stream"},
    )

    row = {
        "id": doc_id,
        "user_id": user_id,
        "doc_type": doc_type.value,
        "filename": filename,
        "storage_path": storage_path,
        "content_type": content_type,
        "size_bytes": len(content),
        "status": DocumentStatus.uploaded.value,
    }
    resp = db.table(TABLE).insert(row).execute()
    return Document(**resp.data[0])


def list_documents(user_id: str) -> list[Document]:
    """Return all documents uploaded by a user, oldest first."""
    db = get_supabase()
    resp = (
        db.table(TABLE)
        .select("*")
        .eq("user_id", user_id)
        .order("created_at")
        .execute()
    )
    return [Document(**row) for row in resp.data]
