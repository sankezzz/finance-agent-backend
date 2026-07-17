"""Prompt for the chat assistant.

Grounds the LLM in the user's computed snapshot (which already encodes the
categorized spending, subscriptions, assets, and liabilities) plus their
profile. The model answers ONLY from these figures — no raw transactions in
the prompt (so no PII), and it must not invent numbers.
"""

from __future__ import annotations

from app.models.financial import Snapshot
from app.models.user import User

CHAT_SYSTEM = (
    "You are the user's personal finance copilot. Answer their questions about "
    "their money in a warm, concise, plain-language way, grounded STRICTLY in "
    "the financial data below. Never invent numbers — if the data doesn't "
    "contain the answer, say so honestly and suggest what would help. All "
    "amounts are Indian Rupees (INR, ₹). Keep answers short and specific; use a "
    "number from the data whenever you make a claim. For 'what if' questions "
    "(saving/growth over years), you may estimate but state your assumptions."
)


def _rupees(x: float | None) -> str:
    return f"Rs {x:,.0f}" if x is not None else "unknown"


def _top_categories(breakdown: dict[str, float], n: int = 6) -> str:
    if not breakdown:
        return "none recorded"
    top = sorted(breakdown.items(), key=lambda kv: -kv[1])[:n]
    return ", ".join(f"{cat} {_rupees(amt)}/mo" for cat, amt in top)


def _goals(user: User | None) -> str:
    if not user or not user.financial_goals:
        return "none stated"
    return "; ".join(
        f"{g.name} ({_rupees(g.target_amount)}"
        + (f" by {g.target_date}" if g.target_date else "")
        + ")"
        for g in user.financial_goals
    )


def build_chat_system(snapshot: Snapshot, user: User | None) -> str:
    """Return the system prompt with the user's financial context injected."""
    runway = (
        f"{snapshot.emergency_runway_months:.1f} months"
        if snapshot.emergency_runway_months is not None
        else "unknown"
    )
    age = user.age if user else "unknown"
    dependents = user.dependents if user else "unknown"

    context = f"""\
USER'S FINANCIAL DATA (monthly figures unless noted; period {snapshot.period_start} to {snapshot.period_end})
- Age: {age} | Dependents: {dependents} | Goals: {_goals(user)}
- Health score: {snapshot.health_score}/100 (savings {snapshot.savings_score}, debt {snapshot.debt_score}, runway {snapshot.runway_score})
- Income: {_rupees(snapshot.monthly_income)}
- Expenses: {_rupees(snapshot.monthly_expenses)} (essential {_rupees(snapshot.essential_expenses)}, discretionary {_rupees(snapshot.discretionary_expenses)})
- Debt payments: {_rupees(snapshot.monthly_debt_payments)} | Investments: {_rupees(snapshot.monthly_investments)}
- Net cash flow: {_rupees(snapshot.net_cash_flow)} | Savings rate: {snapshot.savings_rate * 100:.0f}%
- Debt-to-income: {snapshot.debt_to_income * 100:.0f}% | Emergency runway: {runway}
- Top spending: {_top_categories(snapshot.expense_breakdown)}
- Subscriptions: {snapshot.subscription_count} costing {_rupees(snapshot.subscriptions_monthly)}/mo
- Total assets: {_rupees(snapshot.total_assets)} | Total liabilities: {_rupees(snapshot.total_liabilities)}"""

    return f"{CHAT_SYSTEM}\n\n{context}"
