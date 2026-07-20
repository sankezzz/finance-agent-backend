"""Document Parser Agent (LLM-driven).

For each of the run's uploaded documents:
  download -> extract text (pdf/csv/excel) -> mask PII -> LLM parse into a
  typed ParsedDocument -> persist transactions + financial_facts (tagged
  with run_id) -> mark the document parsed.

One bad document is tolerated (marked failed, others continue); the stage
only fails if every document fails.
"""

from __future__ import annotations

import csv
import io
import logging
import os

from app.agents.base import AgentContext, BaseAgent
from app.config import get_settings
from app.llm.client import get_gemini_structured_llm, get_structured_llm
from app.llm.prompts.parser import PARSER_SYSTEM, build_parser_prompt
from app.core.security import scrub_text
from app.models.document import Document, DocumentStatus
from app.models.fact import FinancialFactCreate
from app.models.parser import ParsedDocument
from app.models.transaction import TransactionCreate
from app.pipeline.stages import Stage
from app.services import document_service, fact_service, transaction_service

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


class ParserAgent(BaseAgent):
    stage = Stage.parse

    def run(self, ctx: AgentContext) -> None:
        documents = document_service.list_documents(ctx.user_id)
        if not documents:
            return

        errors: list[str] = []
        parsed_any = False
        for document in documents:
            try:
                self._process(document, ctx)
                parsed_any = True
            except Exception as exc:  # noqa: BLE001 — isolate per-document failures
                document_service.set_status(document.id, DocumentStatus.failed)
                errors.append(f"{document.filename}: {exc}")

        # Systemic failure (e.g. bad API key) should fail the stage; a single
        # unreadable file should not.
        if not parsed_any:
            raise RuntimeError("Parser failed for all documents: " + "; ".join(errors))

    # -- per-document ------------------------------------------------------

    def _process(self, document: Document, ctx: AgentContext) -> None:
        document_service.set_status(document.id, DocumentStatus.processing)

        raw = document_service.download_document(document.storage_path)
        text = self._extract_text(document.filename, raw)
        if not text.strip():
            raise ValueError("no extractable text found")

        safe_text = scrub_text(text)
        parsed = self._llm_parse(document, safe_text)
        self._persist(parsed, document, ctx)

        document_service.set_status(document.id, DocumentStatus.parsed)

    def _llm_parse(self, document: Document, safe_text: str) -> ParsedDocument:
        settings = get_settings()
        messages = [
            {"role": "system", "content": PARSER_SYSTEM},
            {"role": "user", "content": build_parser_prompt(document.doc_type, safe_text)},
        ]

        # Primary: Gemini (flash-lite) — its 1M TPM / 1,500 RPD free tier dwarfs
        # Groq's 6K TPM / 100K TPD, so full statements parse without hitting the
        # 413/429 walls. Fall back to Groq on ANY failure (rate limit, transient
        # error) or when no Gemini key is configured.
        if settings.GEMINI_API_KEY:
            try:
                return self._parse_with_gemini(messages, settings)
            except Exception as exc:  # noqa: BLE001 — any Gemini failure → Groq
                logger.warning(
                    "Gemini parse failed for %s (%s); falling back to Groq",
                    document.filename,
                    exc,
                )

        return self._parse_with_groq(messages, settings)

    def _parse_with_gemini(self, messages: list[dict], settings) -> ParsedDocument:
        # instructor uses Gemini's native structured-output mode (provider-side
        # schema enforcement) — more reliable than Groq's JSON mode.
        client = get_gemini_structured_llm(settings.PARSER_GEMINI_MODEL)
        return client.create(
            response_model=ParsedDocument,
            temperature=0,
            max_tokens=settings.GROQ_MAX_TOKENS,
            max_retries=2,  # instructor retries on schema-validation failures
            messages=messages,
        )

    def _parse_with_groq(self, messages: list[dict], settings) -> ParsedDocument:
        # JSON mode (not tool-calling): Groq's tool-call schema validation is
        # strict and rejects the small quirks models produce (null vs [], string
        # vs date, anyOf/nullable arrays). JSON mode skips that — instructor
        # parses the JSON and validates with our lenient model instead.
        client = get_structured_llm("json")
        return client.chat.completions.create(
            model=settings.PARSER_GROQ_MODEL,
            response_model=ParsedDocument,
            temperature=0,
            max_tokens=settings.GROQ_MAX_TOKENS,
            max_retries=2,  # instructor retries on schema-validation failures
            messages=messages,
        )

    def _persist(self, parsed: ParsedDocument, document: Document, ctx: AgentContext) -> None:
        doc_meta = {"doc_type": document.doc_type.value}

        transactions = [
            TransactionCreate(
                run_id=ctx.run_id,
                user_id=ctx.user_id,
                document_id=document.id,
                txn_date=t.txn_date,
                description=t.description,
                amount=t.amount,
                direction=t.direction,
                currency=t.currency,
                merchant=t.merchant,
                metadata=doc_meta,
            )
            for t in parsed.transactions
        ]
        facts = [
            FinancialFactCreate(
                run_id=ctx.run_id,
                user_id=ctx.user_id,
                document_id=document.id,
                kind=f.kind,
                subtype=f.subtype,
                label=f.label,
                amount=f.amount,
                currency=f.currency,
                metadata={**f.meta, **doc_meta},
            )
            for f in parsed.facts
        ]

        transaction_service.create_transactions(transactions)
        fact_service.create_facts(facts)

    # -- text extraction ---------------------------------------------------

    def _extract_text(self, filename: str, raw: bytes) -> str:
        ext = os.path.splitext(filename)[1].lower()
        if ext == ".pdf":
            return self._pdf_to_text(raw)
        if ext == ".csv":
            return self._csv_to_text(raw)
        if ext in {".xls", ".xlsx"}:
            return self._excel_to_text(raw)
        if ext in _IMAGE_EXTS:
            raise ValueError("image OCR is not enabled yet")
        raise ValueError(f"unsupported file type '{ext}'")

    def _pdf_to_text(self, raw: bytes) -> str:
        import pypdf

        reader = pypdf.PdfReader(io.BytesIO(raw))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    def _csv_to_text(self, raw: bytes) -> str:
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig", errors="ignore")))
        lines = [" | ".join(c.strip() for c in row if c) for row in reader]
        return "\n".join(line for line in lines if line)

    def _excel_to_text(self, raw: bytes) -> str:
        import openpyxl

        workbook = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
        lines: list[str] = []
        for sheet in workbook.worksheets:
            for row in sheet.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c not in (None, "")]
                if cells:
                    lines.append(" | ".join(cells))
        return "\n".join(lines)
