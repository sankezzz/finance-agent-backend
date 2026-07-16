"""Prompt templates for the Recommendation Agent.

The recommendation quality comes from GROUNDING: the model is fed Agent 3's
exact computed metrics (never raw transactions, so no PII) and is forbidden
from inventing numbers. It must cite the real figures and target the weakest
areas (lowest sub-scores).
"""

from __future__ import annotations

from app.models.financial import Snapshot
from app.models.user import User

RECOMMENDATION_SYSTEM = (
    "You are a pragmatic personal-finance advisor for an Indian user. Give "
    "specific, actionable, honest recommendations grounded STRICTLY in the "
    "figures provided — never invent numbers or assume facts not given. All "
    "amounts are in Indian Rupees (INR). Prioritise the areas where the user is "
    "weakest (lowest sub-scores). Each recommendation must cite the relevant "
    "figure in its rationale and be concrete enough to act on this month. Be "
    "encouraging but direct."
)


def _rupees(x: float | None) -> str:
    return f"Rs {x:,.0f}" if x is not None else "unknown"


def _top_categories(breakdown: dict[str, float], n: int = 4) -> str:
    if not breakdown:
        return "none recorded"
    top = sorted(breakdown.items(), key=lambda kv: -kv[1])[:n]
    return ", ".join(f"{cat} {_rupees(amt)}/mo" for cat, amt in top)


def _goals(user: User | None) -> str:
    if not user or not user.financial_goals:
        return "none stated"
    parts = []
    for g in user.financial_goals:
        by = f" by {g.target_date}" if g.target_date else ""
        parts.append(f"{g.name} ({_rupees(g.target_amount)}{by})")
    return "; ".join(parts)


def build_recommendation_prompt(snapshot: Snapshot, user: User | None) -> str:
    """Render the grounded metrics + user context into the advisor prompt."""
    runway = (
        f"{snapshot.emergency_runway_months:.1f} months"
        if snapshot.emergency_runway_months is not None
        else "unknown (no assets recorded)"
    )
    age = user.age if user else "unknown"
    dependents = user.dependents if user else "unknown"

    return f"""\
Here is the user's computed monthly financial picture. Use ONLY these figures.

PROFILE
- Age: {age} | Dependents: {dependents}
- Financial goals: {_goals(user)}

HEALTH SCORE: {snapshot.health_score}/100
- savings sub-score: {snapshot.savings_score}/100
- debt sub-score:    {snapshot.debt_score}/100
- runway sub-score:  {snapshot.runway_score}/100

CASH FLOW (monthly)
- Income:            {_rupees(snapshot.monthly_income)}
- Expenses:          {_rupees(snapshot.monthly_expenses)} (essential {_rupees(snapshot.essential_expenses)}, discretionary {_rupees(snapshot.discretionary_expenses)})
- Debt payments:     {_rupees(snapshot.monthly_debt_payments)}
- Investments:       {_rupees(snapshot.monthly_investments)}
- Net cash flow:     {_rupees(snapshot.net_cash_flow)}
- Top spend:         {_top_categories(snapshot.expense_breakdown)}
- Subscriptions:     {snapshot.subscription_count} costing {_rupees(snapshot.subscriptions_monthly)}/mo

RATIOS & BALANCE SHEET
- Savings rate:      {snapshot.savings_rate * 100:.0f}%
- Debt-to-income:    {snapshot.debt_to_income * 100:.0f}%
- Emergency runway:  {runway}
- Total assets:      {_rupees(snapshot.total_assets)}
- Total liabilities: {_rupees(snapshot.total_liabilities)}

Write a 1-2 sentence overall summary, then 3-5 prioritized recommendations.
Each must: target a weak area, cite the specific figure above in its rationale,
and give one concrete action with a number where possible.\
"""
