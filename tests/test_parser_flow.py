"""End-to-end parser test for a single PDF.

Drives the real endpoints (onboarding, documents) via an in-process
TestClient, then runs the parser stages inline so every step is visible in
the terminal:

    EXTRACTED text  ->  MASKED text  ->  GROQ output  ->  SAVED rows

The inline parse mirrors exactly what ParserAgent.run() does inside the
pipeline background task; it's run step-by-step here only so we can print
each intermediate stage (the endpoints hide them).

Prereqs:
  * db/schema.sql applied in Supabase
  * .env populated (SUPABASE_URL, SUPABASE_SECRET_KEY, GROQ_API_KEY)

Usage:
  python tests/test_parser_flow.py path/to/statement.pdf --doc-type bank_statement
  python tests/test_parser_flow.py stmt.pdf --user-id <existing-user-id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys

# Allow running as `python tests/test_parser_flow.py` from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.agents.base import AgentContext  # noqa: E402
from app.agents.parser_agent import ParserAgent  # noqa: E402
from app.core.security import scrub_text  # noqa: E402
from app.main import app  # noqa: E402
from app.models.document import Document, DocumentStatus  # noqa: E402
from app.models.pipeline import StageStatus  # noqa: E402
from app.pipeline.stages import Stage  # noqa: E402
from app.services import (  # noqa: E402
    document_service,
    fact_service,
    pipeline_service,
    transaction_service,
)

client = TestClient(app)


# -- pretty printing --------------------------------------------------------

def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def preview(text: str, limit: int = 1500) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + f"\n... [truncated, {len(text)} chars total]"


def dump(obj) -> str:
    return json.dumps(obj, indent=2, default=str, ensure_ascii=False)


# -- flow -------------------------------------------------------------------

def check_health() -> None:
    section("1. GET /health")
    resp = client.get("/health")
    print(resp.status_code, resp.json())
    assert resp.status_code == 200


def onboard(user_id: str | None) -> str:
    section("2. POST /onboarding")
    if user_id:
        resp = client.get(f"/onboarding/{user_id}")
        print(f"reusing user {user_id}:", resp.status_code)
        assert resp.status_code == 200, "given --user-id not found"
        return user_id

    payload = {
        "name": "Parser Test",
        "age": 30,
        "monthly_income": 80000,
        "dependents": 0,
        "existing_loans": [],
        "financial_goals": [],
    }
    resp = client.post("/onboarding", json=payload)
    print(resp.status_code)
    assert resp.status_code == 201, resp.text
    uid = resp.json()["id"]
    print("created user_id:", uid)
    return uid


def upload(pdf_path: str, doc_type: str, user_id: str) -> Document:
    section("3. POST /documents  (upload)")
    filename = os.path.basename(pdf_path)
    with open(pdf_path, "rb") as fh:
        resp = client.post(
            "/documents",
            data={"user_id": user_id, "doc_type": doc_type},
            files={"file": (filename, fh, "application/pdf")},
        )
    print(resp.status_code)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    print(dump(body))

    section("3b. GET /documents  (list)")
    listed = client.get("/documents", params={"user_id": user_id})
    print(listed.status_code, f"{len(listed.json())} document(s)")
    return Document(**body)


def parse_inline(document: Document, user_id: str) -> str:
    """Run the parser's stages one by one, printing each. Returns the run_id."""
    run = pipeline_service.create_run(user_id)
    run_id = str(run.id)
    print(f"\ncreated run_id: {run_id}")

    agent = ParserAgent()
    ctx = AgentContext(run_id=run_id, user_id=user_id)

    pipeline_service.set_stage(run_id, Stage.parse, StageStatus.running)
    document_service.set_status(document.id, DocumentStatus.processing)

    # Step: download + extract
    raw = document_service.download_document(document.storage_path)
    text = agent._extract_text(document.filename, raw)
    section("4. EXTRACTED TEXT (raw, from the file)")
    print(preview(text))

    # Step: mask
    safe = scrub_text(text)
    section("5. MASKED TEXT (what actually goes to the LLM)")
    print(preview(safe))

    # Step: LLM parse
    section("6. GROQ OUTPUT (validated ParsedDocument)")
    parsed = agent._llm_parse(document, safe)
    print(dump(parsed.model_dump()))

    # Step: persist
    agent._persist(parsed, document, ctx)
    document_service.set_status(document.id, DocumentStatus.parsed)
    pipeline_service.set_stage(run_id, Stage.parse, StageStatus.done)
    return run_id


def show_saved(run_id: str) -> None:
    section("7. SAVED — transactions")
    txns = transaction_service.list_transactions(run_id)
    print(f"{len(txns)} transaction(s)")
    print(dump([t.model_dump() for t in txns]))

    section("8. SAVED — financial_facts")
    facts = fact_service.list_facts(run_id)
    print(f"{len(facts)} fact(s)")
    print(dump([f.model_dump() for f in facts]))

    section("9. GET /pipeline/runs/{run_id}")
    resp = client.get(f"/pipeline/runs/{run_id}")
    print(resp.status_code)
    print(dump(resp.json()))


def main() -> None:
    ap = argparse.ArgumentParser(description="Parser end-to-end test on one PDF.")
    ap.add_argument("pdf", help="path to a PDF to parse")
    ap.add_argument(
        "--doc-type",
        default="bank_statement",
        help="bank_statement | credit_card_statement | salary_slip | investment_statement | loan_statement",
    )
    ap.add_argument("--user-id", default=None, help="reuse an existing user id")
    args = ap.parse_args()

    if not os.path.isfile(args.pdf):
        sys.exit(f"file not found: {args.pdf}")

    check_health()
    user_id = onboard(args.user_id)
    document = upload(args.pdf, args.doc_type, user_id)
    run_id = parse_inline(document, user_id)
    show_saved(run_id)

    section("DONE")
    print(f"user_id={user_id}")
    print(f"run_id={run_id}")
    print("Inspect in Supabase: select * from transactions where run_id = '%s';" % run_id)


if __name__ == "__main__":
    main()
