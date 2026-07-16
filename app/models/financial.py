"""Financial snapshot, metrics, and profile schemas.

Metrics: the numbers produced by core/finance from a run's transactions +
facts (savings rate, debt ratio, emergency runway, health score). Pure
output — no DB fields.
Snapshot: a stored Metrics row (adds id/run_id/user_id/created_at).
"""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MonthPoint(BaseModel):
    """One month of the spending trend."""

    month: str  # "YYYY-MM"
    expenses: float = 0.0
    debt: float = 0.0
    investments: float = 0.0


class Metrics(BaseModel):
    """Computed financial metrics for one run. All money values are MONTHLY."""

    period_start: date | None = None
    period_end: date | None = None
    months: float = 1.0

    monthly_income: float = 0.0
    monthly_expenses: float = 0.0          # consumption only (excl. debt/investment)
    monthly_debt_payments: float = 0.0     # EMI / loan servicing
    monthly_investments: float = 0.0       # SIP / MF outflows (this is savings)
    net_cash_flow: float = 0.0             # income - expenses - debt_payments

    # Needs vs wants (both subsets of monthly_expenses).
    essential_expenses: float = 0.0        # Rent, Utilities, Health, Food
    discretionary_expenses: float = 0.0    # Shopping, Travel, Entertainment, Other

    # Recurring subscriptions (from the is_subscription flag).
    subscription_count: int = 0
    subscriptions_monthly: float = 0.0

    savings_rate: float = 0.0              # net_cash_flow / income
    debt_to_income: float = 0.0            # debt_payments / income
    total_assets: float = 0.0
    total_liabilities: float = 0.0
    emergency_runway_months: float | None = None

    health_score: float = 0.0
    savings_score: float = 0.0
    debt_score: float = 0.0
    runway_score: float = 0.0

    expense_breakdown: dict[str, float] = Field(default_factory=dict)  # category -> monthly
    monthly_trend: list[MonthPoint] = Field(default_factory=list)      # spending over time


class Snapshot(Metrics):
    """A stored financial snapshot row."""

    id: UUID
    run_id: UUID
    user_id: UUID
    created_at: datetime
