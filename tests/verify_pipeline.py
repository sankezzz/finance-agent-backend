"""Full end-to-end pipeline verification.

Exercises the REAL code path through the actual HTTP endpoints (in-process via
TestClient — no separate server needed):

    /health → POST /onboarding → POST /documents (xN) → POST /pipeline/runs
            → poll GET /pipeline/runs/{id} → GET /dashboard/{user_id}

and verifies every stage completes and data lands in every table
(transactions, financial_facts, financial_snapshots, recommendations).

Note: with TestClient, FastAPI background tasks run synchronously during the
POST /pipeline/runs call, so that call blocks while all 4 agents run (~30-90s).

Usage:
  python tests/verify_pipeline.py dummy_data/
  python tests/verify_pipeline.py dummy_data/ --user-id <uuid>   # reuse a user
"""

from __future__ import annotations

import argparse
import os
import sys
from time import sleep

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import (  # noqa: E402
    fact_service,
    financial_service,
    recommendation_service,
    transaction_service,
)

client = TestClient(app)

SUPPORTED_EXTS = {".pdf", ".csv", ".xls", ".xlsx", ".png", ".jpg", ".jpeg"}
POLL_TIMEOUT_S = 240
POLL_INTERVAL_S = 2

_checks: list[tuple[bool, str]] = []


def check(ok: bool, label: str, detail: str = "") -> bool:
    _checks.append((ok, label))
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail else ""))
    return ok


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def infer_doc_type(filename: str) -> str:
    n = filename.lower()
    if "credit" in n or "card" in n:
        return "credit_card_statement"
    if "salary" in n or "payslip" in n or "slip" in n:
        return "salary_slip"
    if "loan" in n:
        return "loan_statement"
    if any(k in n for k in ("invest", "mutual", "portfolio", "fd", "stock", "groww")):
        return "investment_statement"
    return "bank_statement"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--user-id", default=None)
    args = ap.parse_args()

    if not os.path.isdir(args.folder):
        sys.exit(f"not a folder: {args.folder}")

    # 1. health
    section("1. HEALTH")
    r = client.get("/health")
    check(r.status_code == 200 and r.json().get("status") == "ok", "GET /health", str(r.status_code))

    # 2. onboarding
    section("2. ONBOARDING")
    if args.user_id:
        user_id = args.user_id
        r = client.get(f"/onboarding/{user_id}")
        check(r.status_code == 200, "reuse user", user_id)
    else:
        r = client.post("/onboarding", json={
            "name": "E2E Verify", "age": 30, "monthly_income": 80000,
            "dependents": 0, "existing_loans": [], "financial_goals": [],
        })
        ok = check(r.status_code == 201, "POST /onboarding", str(r.status_code))
        if not ok:
            print(r.text)
            _finish()
        user_id = r.json()["id"]
    print(f"  user_id = {user_id}")

    # 3. upload
    section("3. DOCUMENT UPLOAD")
    files = sorted(f for f in os.listdir(args.folder)
                   if os.path.splitext(f)[1].lower() in SUPPORTED_EXTS)
    check(len(files) > 0, "files found", f"{len(files)} file(s)")
    for name in files:
        doc_type = infer_doc_type(name)
        with open(os.path.join(args.folder, name), "rb") as fh:
            r = client.post("/documents",
                            data={"user_id": user_id, "doc_type": doc_type},
                            files={"file": (name, fh, "application/octet-stream")})
        check(r.status_code == 201, f"upload {name}", f"-> {doc_type}")

    # 4. trigger run  (background runs all 4 agents synchronously under TestClient)
    section("4. TRIGGER RUN  (runs all 4 agents — may take ~30-90s)")
    r = client.post("/pipeline/runs", json={"user_id": user_id})
    ok = check(r.status_code == 202, "POST /pipeline/runs", str(r.status_code))
    if not ok:
        print(r.text)
        _finish()
    run_id = r.json()["id"]
    print(f"  run_id = {run_id}")

    # 5. poll status
    section("5. POLL STATUS")
    status, run = "pending", None
    waited = 0
    while waited <= POLL_TIMEOUT_S:
        r = client.get(f"/pipeline/runs/{run_id}")
        run = r.json()
        status = run["status"]
        if status in ("done", "failed"):
            break
        sleep(POLL_INTERVAL_S)
        waited += POLL_INTERVAL_S
    check(status == "done", "run status == done", status + (f" — {run.get('error')}" if run and run.get("error") else ""))
    if run:
        for s in run["stages"]:
            check(s["status"] == "done", f"stage {s['stage']}", s["status"])

    # 6. verify data landed
    section("6. DATA LANDED")
    txns = transaction_service.list_transactions(run_id)
    facts = fact_service.list_facts(run_id)
    snap = financial_service.get_snapshot(run_id)
    recs = recommendation_service.get(run_id)
    check(len(txns) > 0, "transactions written", f"{len(txns)} rows")
    check(len(facts) > 0, "financial_facts written", f"{len(facts)} rows")
    check(snap is not None, "snapshot written", f"health={snap.health_score}" if snap else "missing")
    check(bool(txns) and all(t.category for t in txns), "all transactions categorized",
          f"{sum(1 for t in txns if not t.category)} uncategorized")
    check(recs is not None and len(recs.recommendations) > 0,
          "recommendations written", f"{len(recs.recommendations)}" if recs else "missing")

    # 7. dashboard endpoint
    section("7. DASHBOARD ENDPOINT")
    r = client.get(f"/dashboard/{user_id}")
    ok = check(r.status_code == 200, "GET /dashboard/{user_id}", str(r.status_code))
    if ok:
        d = r.json()
        check(d["metrics"]["health_score"] is not None, "dashboard has metrics",
              f"health={d['metrics']['health_score']}")
        check("recommendations" in d, "dashboard has recommendations",
              f"{len(d.get('recommendations', []))}")

    _finish(user_id, run_id)


def _finish(user_id: str = "", run_id: str = "") -> None:
    section("RESULT")
    passed = sum(1 for ok, _ in _checks if ok)
    total = len(_checks)
    failed = [label for ok, label in _checks if not ok]
    print(f"  {passed}/{total} checks passed")
    if failed:
        print("  FAILED:")
        for label in failed:
            print(f"    - {label}")
    if user_id:
        print(f"\n  user_id={user_id}")
    if run_id:
        print(f"  run_id={run_id}")
    print("\n  " + ("✅ PIPELINE VERIFIED" if not failed else "❌ VERIFICATION FAILED"))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
