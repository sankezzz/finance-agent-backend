"""Run the recommendation agent over a run and print the advice.

Requires a run that already has a financial snapshot (analysis complete).

Usage:
  python tests/test_recommendation.py <run_id>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.base import AgentContext  # noqa: E402
from app.agents.recommendation_agent import RecommendationAgent  # noqa: E402
from app.services import financial_service, pipeline_service, recommendation_service  # noqa: E402


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python tests/test_recommendation.py <run_id>")
    run_id = sys.argv[1]

    run = pipeline_service.get_run(run_id)
    if run is None:
        sys.exit(f"run not found: {run_id}")
    if financial_service.get_snapshot(run_id) is None:
        sys.exit("no snapshot for this run — run analysis first")

    section("generating recommendations…")
    RecommendationAgent().run(AgentContext(run_id=run_id, user_id=str(run.user_id)))

    rec = recommendation_service.get(run_id)
    if rec is None:
        sys.exit("no recommendations produced")

    section("SUMMARY")
    print(f"  {rec.summary}")

    section(f"RECOMMENDATIONS ({len(rec.recommendations)})")
    order = {"high": 0, "medium": 1, "low": 2}
    for r in sorted(rec.recommendations, key=lambda x: order.get(x.priority.value, 3)):
        print(f"\n  [{r.priority.value.upper()}] {r.title}   ({r.category.value})")
        print(f"     why:    {r.rationale}")
        print(f"     action: {r.action}")

    section("DONE")
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
