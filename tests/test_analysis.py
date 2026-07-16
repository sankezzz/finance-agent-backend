"""Run the analysis agent over a run and print the computed snapshot.

Requires a run whose transactions are already parsed + categorized.

Usage:
  python tests/test_analysis.py <run_id>
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agents.analysis_agent import AnalysisAgent  # noqa: E402
from app.agents.base import AgentContext  # noqa: E402
from app.services import financial_service, pipeline_service  # noqa: E402


def section(title: str) -> None:
    print("\n" + "=" * 72)
    print(f"  {title}")
    print("=" * 72)


def money(x) -> str:
    return f"{x:,.2f}" if x is not None else "—"


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit("usage: python tests/test_analysis.py <run_id>")
    run_id = sys.argv[1]

    run = pipeline_service.get_run(run_id)
    if run is None:
        sys.exit(f"run not found: {run_id}")

    section("running analysis agent…")
    AnalysisAgent().run(AgentContext(run_id=run_id, user_id=str(run.user_id)))

    snap = financial_service.get_snapshot(run_id)
    if snap is None:
        sys.exit("no snapshot produced")

    section(f"SNAPSHOT  (period {snap.period_start} → {snap.period_end}, {snap.months:.0f} month(s))")
    print(f"  monthly income          {money(snap.monthly_income)}")
    print(f"  monthly expenses        {money(snap.monthly_expenses)}   (consumption)")
    print(f"    · essential           {money(snap.essential_expenses)}")
    print(f"    · discretionary       {money(snap.discretionary_expenses)}")
    print(f"  monthly debt payments   {money(snap.monthly_debt_payments)}")
    print(f"  monthly investments     {money(snap.monthly_investments)}   (savings)")
    print(f"  subscriptions           {money(snap.subscriptions_monthly)}/mo across {snap.subscription_count}")
    print(f"  net cash flow           {money(snap.net_cash_flow)}")
    print(f"  total assets            {money(snap.total_assets)}")
    print(f"  total liabilities       {money(snap.total_liabilities)}")

    section("RATIOS & SCORE")
    print(f"  savings rate            {snap.savings_rate * 100:.1f}%   (score {snap.savings_score})")
    print(f"  debt-to-income          {snap.debt_to_income * 100:.1f}%   (score {snap.debt_score})")
    runway = f"{snap.emergency_runway_months:.1f} months" if snap.emergency_runway_months is not None else "—"
    print(f"  emergency runway        {runway}   (score {snap.runway_score})")
    print(f"  ──────────────────────────────")
    print(f"  HEALTH SCORE            {snap.health_score} / 100")

    section("MONTHLY EXPENSE BREAKDOWN")
    for cat, amt in sorted(snap.expense_breakdown.items(), key=lambda kv: -kv[1]):
        print(f"  {cat:16s} {money(amt)}")

    section("SPENDING TREND (per month)")
    print(f"  {'month':10s} {'expenses':>12s} {'debt':>12s} {'investments':>12s}")
    for p in snap.monthly_trend:
        print(f"  {p.month:10s} {money(p.expenses):>12s} {money(p.debt):>12s} {money(p.investments):>12s}")

    section("DONE")
    print(f"run_id={run_id}")


if __name__ == "__main__":
    main()
