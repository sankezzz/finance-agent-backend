"""Run the categorizer over an already-parsed run and show the result.

Reuses a run whose transactions the parser already produced (so no
re-parsing / minimal LLM cost — only the unknown-merchant fallback call
fires), then prints the category breakdown, recurring count, and the
detected subscriptions.

Usage:
  python tests/test_categorizer.py <run_id>
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.base import AgentContext  # noqa: E402
from app.agents.categorizer_agent import CategorizerAgent  # noqa: E402
from app.services import pipeline_service, transaction_service  # noqa: E402


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python tests/test_categorizer.py <run_id>")
    run_id = sys.argv[1]

    run = pipeline_service.get_run(run_id)
    if run is None:
        sys.exit(f"run not found: {run_id}")

    before = transaction_service.list_transactions(run_id)
    section("BEFORE")
    uncategorized = sum(1 for t in before if not t.category)
    print(f"{len(before)} transactions | {uncategorized} uncategorized")
    if not before:
        sys.exit("no transactions for this run — parse a run first")

    section("running categorizer…")
    CategorizerAgent().run(AgentContext(run_id=run_id, user_id=str(run.user_id)))

    after = transaction_service.list_transactions(run_id)

    # Category breakdown (count + total amount).
    by_cat: dict[str, list] = defaultdict(list)
    for t in after:
        by_cat[t.category or "(none)"].append(t)

    section("CATEGORY BREAKDOWN")
    print(f"{'category':16s} {'count':>6s} {'total amount':>15s}")
    for cat in sorted(by_cat, key=lambda c: -sum(t.amount for t in by_cat[c])):
        items = by_cat[cat]
        print(f"{cat:16s} {len(items):6d} {sum(t.amount for t in items):15,.2f}")

    recurring = [t for t in after if t.is_recurring]
    subs = [t for t in after if t.is_subscription]

    section(f"RECURRING: {len(recurring)} transactions")
    section(f"SUBSCRIPTIONS: {len(subs)} transactions")
    seen = set()
    for t in subs:
        m = (t.merchant or t.description)[:40]
        if m not in seen:
            seen.add(m)
            print(f"  {m:40s} {t.amount:>10,.2f}  [{t.category}]")

    section("SAMPLE (first 15 transactions)")
    for t in after[:15]:
        flags = ("R" if t.is_recurring else "-") + ("S" if t.is_subscription else "-")
        print(f"  {flags}  {t.category or '?':14s} {t.amount:>10,.2f}  {(t.merchant or t.description)[:40]}")

    section("DONE")
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
