"""End-to-end parser test for MULTIPLE documents in ONE run.

Uploads every supported file in a folder (one POST /documents per file,
each tagged with a doc_type inferred from its name), then runs the parser
over all of them under a single run_id — exactly what POST /pipeline/runs
does in the background. Prints per-document timing + counts, surfaces Groq
rate-limits (429) clearly, and dumps the saved rows at the end.

Prereqs:
  * db/schema.sql applied in Supabase
  * .env populated (SUPABASE_URL, SUPABASE_SECRET_KEY, GROQ_API_KEY)

Usage:
  python tests/test_parser_multi.py dummy_data/
  python tests/test_parser_multi.py dummy_data/ --verbose        # full Groq JSON
  python tests/test_parser_multi.py dummy_data/ --delay 2        # 2s between docs
  python tests/test_parser_multi.py dummy_data/ --user-id <uuid> # reuse a user
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from time import perf_counter, sleep

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

SUPPORTED_EXTS = {".pdf", ".csv", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}


# -- helpers ----------------------------------------------------------------

def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def dump(obj) -> str:
    return json.dumps(obj, indent=2, default=str, ensure_ascii=False)


def infer_doc_type(filename: str) -> str:
    n = filename.lower()
    if "credit" in n or "card" in n:
        return "credit_card_statement"
    if "salary" in n or "payslip" in n or "slip" in n:
        return "salary_slip"
    if "loan" in n:
        return "loan_statement"
    if any(k in n for k in ("invest", "mutual", "portfolio", "fd", "stock")):
        return "investment_statement"
    return "bank_statement"  # sensible default (covers "bank"/"statement"/"account")


def is_rate_limit(exc: Exception) -> bool:
    if type(exc).__name__ == "RateLimitError":
        return True
    if getattr(exc, "status_code", None) == 429:
        return True
    return "rate limit" in str(exc).lower() or "429" in str(exc)


# -- flow -------------------------------------------------------------------

def onboard(user_id: str | None) -> str:
    section("onboarding")
    if user_id:
        resp = client.get(f"/onboarding/{user_id}")
        assert resp.status_code == 200, "given --user-id not found"
        print("reusing user:", user_id)
        return user_id
    resp = client.post(
        "/onboarding",
        json={"name": "Multi Test", "age": 30, "monthly_income": 80000,
              "dependents": 0, "existing_loans": [], "financial_goals": []},
    )
    assert resp.status_code == 201, resp.text
    uid = resp.json()["id"]
    print("created user:", uid)
    return uid


def upload_folder(folder: str, user_id: str) -> list[Document]:
    files = sorted(
        f for f in os.listdir(folder)
        if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS
    )
    if not files:
        sys.exit(f"no supported files in {folder}")

    section(f"uploading {len(files)} document(s) — inferred types")
    documents: list[Document] = []
    for name in files:
        doc_type = infer_doc_type(name)
        path = os.path.join(folder, name)
        with open(path, "rb") as fh:
            resp = client.post(
                "/documents",
                data={"user_id": user_id, "doc_type": doc_type},
                files={"file": (name, fh, "application/octet-stream")},
            )
        status = "OK" if resp.status_code == 201 else f"FAIL {resp.status_code}"
        print(f"  [{status}] {name:40s} -> {doc_type}")
        if resp.status_code == 201:
            documents.append(Document(**resp.json()))
        else:
            print("       ", resp.text)
    return documents


def parse_all(documents: list[Document], user_id: str, *, verbose: bool, delay: float) -> str:
    run = pipeline_service.create_run(user_id)
    run_id = str(run.id)
    section(f"parsing under one run_id = {run_id}")

    agent = ParserAgent()
    ctx = AgentContext(run_id=run_id, user_id=user_id)
    pipeline_service.set_stage(run_id, Stage.parse, StageStatus.running)

    results = []
    for i, doc in enumerate(documents):
        if i and delay:
            sleep(delay)
        t0 = perf_counter()
        try:
            document_service.set_status(doc.id, DocumentStatus.processing)
            raw = document_service.download_document(doc.storage_path)
            text = agent._extract_text(doc.filename, raw)
            if not text.strip():
                raise ValueError("no extractable text (scanned image PDF?)")
            parsed = agent._llm_parse(doc, scrub_text(text))
            agent._persist(parsed, doc, ctx)
            document_service.set_status(doc.id, DocumentStatus.parsed)
            dt = perf_counter() - t0
            print(f"  [OK]   {doc.filename:40s} {dt:5.1f}s  "
                  f"chars={len(text):6d}  txns={len(parsed.transactions):3d}  facts={len(parsed.facts):3d}")
            if verbose:
                print(dump(parsed.model_dump()))
            results.append((doc.filename, "ok", None))
        except Exception as exc:  # noqa: BLE001
            dt = perf_counter() - t0
            tag = "RATE-LIMIT" if is_rate_limit(exc) else "FAIL"
            print(f"  [{tag}] {doc.filename:40s} {dt:5.1f}s  {exc}")
            document_service.set_status(doc.id, DocumentStatus.failed)
            results.append((doc.filename, tag.lower(), str(exc)))

    pipeline_service.set_stage(run_id, Stage.parse, StageStatus.done)

    section("per-document summary")
    for name, status, err in results:
        print(f"  {status.upper():11s} {name}" + (f"  — {err}" if err else ""))
    return run_id


def show_saved(run_id: str) -> None:
    txns = transaction_service.list_transactions(run_id)
    facts = fact_service.list_facts(run_id)

    section(f"SAVED — {len(txns)} transactions, {len(facts)} facts (run {run_id})")
    print("\ntransactions (first 20):")
    print(dump([t.model_dump() for t in txns[:20]]))
    print("\nfinancial_facts:")
    print(dump([f.model_dump() for f in facts]))


def main() -> None:
    ap = argparse.ArgumentParser(description="Parse a folder of documents in one run.")
    ap.add_argument("folder", help="folder containing the documents (e.g. dummy_data/)")
    ap.add_argument("--user-id", default=None, help="reuse an existing user id")
    ap.add_argument("--verbose", action="store_true", help="print full Groq output per doc")
    ap.add_argument("--delay", type=float, default=0.0, help="seconds to wait between docs")
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        sys.exit(f"not a folder: {args.folder}")

    t0 = perf_counter()
    user_id = onboard(args.user_id)
    documents = upload_folder(args.folder, user_id)
    run_id = parse_all(documents, user_id, verbose=args.verbose, delay=args.delay)
    show_saved(run_id)

    section("DONE")
    print(f"user_id={user_id}")
    print(f"run_id={run_id}")
    print(f"total wall time: {perf_counter() - t0:.1f}s")


if __name__ == "__main__":
    main()
