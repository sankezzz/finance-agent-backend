"""Document upload routes.

Endpoints for uploading financial documents by type (bank statement,
credit card statement, salary slip, investment statement, loan statement)
and listing a user's uploaded documents. One file per request, tagged
with its declared type.
"""

import os

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.models.document import Document, DocumentType
from app.services import document_service, onboarding_service

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_EXTENSIONS = {".pdf", ".csv", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}


@router.post("", response_model=Document, status_code=201)
async def upload_document(
    user_id: str = Form(...),
    doc_type: DocumentType = Form(...),
    file: UploadFile = File(...),
) -> Document:
    """Store one uploaded document for a user and record it."""
    if onboarding_service.get_user(user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
        )

    content = await file.read()
    return document_service.create_document(
        user_id=user_id,
        doc_type=doc_type,
        filename=file.filename,
        content_type=file.content_type,
        content=content,
    )


@router.get("", response_model=list[Document])
def list_documents(user_id: str) -> list[Document]:
    """List all documents a user has uploaded."""
    return document_service.list_documents(user_id)
