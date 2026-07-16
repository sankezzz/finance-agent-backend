"""Pure financial calculations.

Deterministic functions for savings rate, debt-to-income, emergency runway,
and the overall health score, plus `compute_metrics` which turns a run's
transactions + facts into a Metrics object. NO DB, NO LLM, NO I/O — this is
what makes the numbers testable and auditable independent of any agent.

Definitions (all money values are normalised to MONTHLY over the observed
transaction period):
  monthly_income        net salary (fact) > Income-category credits > declared
  monthly_expenses      consumption-category debits (Food..Health, Other)
  monthly_debt_payments EMI_Loan debits (fallback: loan facts' emi meta)
  monthly_investments   Investment-category debits (counted as SAVINGS, not spend)
  net_cash_flow         income - expenses - debt_payments   (== amount saved)
  savings_rate          net_cash_flow / income
  debt_to_income        debt_payments / income
  emergency_runway      total_assets / (expenses + debt_payments)
  health_score          weighted blend of savings/debt/runway sub-scores
"""

from __future__ import annotations

from app.models.fact import FactKind, FinancialFact
from app.models.financial import Metrics, MonthPoint
from app.models.transaction import Transaction, TransactionCategory, TransactionDirection

# Which categories count where. Essential + discretionary partition consumption.
_ESSENTIAL = {
    TransactionCategory.rent.value,
    TransactionCategory.utilities.value,
    TransactionCategory.health.value,
    TransactionCategory.food.value,
}
_DISCRETIONARY = {
    TransactionCategory.shopping.value,
    TransactionCategory.travel.value,
    TransactionCategory.entertainment.value,
    TransactionCategory.other.value,
}
_CONSUMPTION = _ESSENTIAL | _DISCRETIONARY
_DEBT = {TransactionCategory.emi_loan.value}
_INVESTMENT = {TransactionCategory.investment.value}

# Health-score tuning (documented, transparent).
_SAVINGS_TARGET = 0.20   # 20% savings rate == full marks
_DTI_CEILING = 0.40      # 40% debt-to-income == zero marks
_RUNWAY_TARGET = 6.0     # 6 months == full marks
_W_SAVINGS, _W_DEBT, _W_RUNWAY = 0.40, 0.30, 0.30


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def savings_rate(income: float, expenses: float, debt_payments: float) -> float:
    if income <= 0:
        return 0.0
    return (income - expenses - debt_payments) / income


def debt_to_income(debt_payments: float, income: float) -> float:
    if income <= 0:
        return 0.0
    return debt_payments / income


def emergency_runway(liquid_assets: float, monthly_outflow: float) -> float | None:
    if monthly_outflow <= 0:
        return None
    return liquid_assets / monthly_outflow


def health_score(sr: float, dti: float, runway: float | None) -> tuple[float, float, float, float]:
    """Return (overall, savings_score, debt_score, runway_score), each 0-100."""
    savings_score = _clamp(sr / _SAVINGS_TARGET) * 100
    debt_score = _clamp(1 - dti / _DTI_CEILING) * 100
    runway_score = _clamp((runway or 0.0) / _RUNWAY_TARGET) * 100
    overall = _W_SAVINGS * savings_score + _W_DEBT * debt_score + _W_RUNWAY * runway_score
    return round(overall, 1), round(savings_score, 1), round(debt_score, 1), round(runway_score, 1)


def _months_observed(dates: list) -> int:
    if not dates:
        return 1
    return max(len({(d.year, d.month) for d in dates}), 1)


def compute_metrics(
    *,
    transactions: list[Transaction],
    facts: list[FinancialFact],
    declared_income: float | None = None,
) -> Metrics:
    """Turn a run's categorized transactions + facts into monthly Metrics."""
    dated = [t.txn_date for t in transactions if t.txn_date]
    months = _months_observed(dated)

    consumption = debt = investment = income_credits = 0.0
    essential = discretionary = 0.0
    breakdown: dict[str, float] = {}
    trend: dict[str, dict[str, float]] = {}
    for t in transactions:
        cat = t.category or TransactionCategory.other.value
        month_key = f"{t.txn_date.year:04d}-{t.txn_date.month:02d}" if t.txn_date else None
        slot = trend.setdefault(month_key, {"expenses": 0.0, "debt": 0.0, "investments": 0.0}) if month_key else None
        if t.direction == TransactionDirection.debit:
            if cat in _CONSUMPTION:
                consumption += t.amount
                breakdown[cat] = breakdown.get(cat, 0.0) + t.amount
                if cat in _ESSENTIAL:
                    essential += t.amount
                else:
                    discretionary += t.amount
                if slot is not None:
                    slot["expenses"] += t.amount
            elif cat in _DEBT:
                debt += t.amount
                if slot is not None:
                    slot["debt"] += t.amount
            elif cat in _INVESTMENT:
                investment += t.amount
                if slot is not None:
                    slot["investments"] += t.amount
            # Transfer / ATM cash / card-bill payments are excluded from ratios.
        elif cat == TransactionCategory.income.value:
            income_credits += t.amount

    monthly_expenses = consumption / months
    monthly_debt = debt / months
    monthly_investments = investment / months
    expense_breakdown = {k: round(v / months, 2) for k, v in breakdown.items()}
    monthly_trend = [
        MonthPoint(
            month=key,
            expenses=round(vals["expenses"], 2),
            debt=round(vals["debt"], 2),
            investments=round(vals["investments"], 2),
        )
        for key, vals in sorted(trend.items())
    ]

    # Recurring subscriptions (flagged by the categorizer).
    sub_txns = [t for t in transactions if t.is_subscription]
    subscription_count = len({(t.merchant or t.description).strip().lower() for t in sub_txns})
    subscriptions_monthly = sum(t.amount for t in sub_txns) / months

    # Income: prefer net salary (doc-derived) > income credits > declared onboarding value.
    net_salary = sum(
        f.amount for f in facts
        if f.kind == FactKind.income and f.subtype.lower() in ("salary", "net_salary")
    )
    if net_salary > 0:
        monthly_income = net_salary
    elif income_credits > 0:
        monthly_income = income_credits / months
    else:
        monthly_income = declared_income or 0.0

    # If no EMI transactions were seen, fall back to loan facts' declared emi.
    if monthly_debt == 0:
        monthly_debt = sum(
            float(f.metadata.get("emi") or 0)
            for f in facts
            if f.kind == FactKind.liability
        )

    total_assets = sum(f.amount for f in facts if f.kind == FactKind.asset)
    total_liabilities = sum(f.amount for f in facts if f.kind == FactKind.liability)

    monthly_outflow = monthly_expenses + monthly_debt
    net_cash_flow = monthly_income - monthly_outflow
    sr = savings_rate(monthly_income, monthly_expenses, monthly_debt)
    dti = debt_to_income(monthly_debt, monthly_income)
    runway = emergency_runway(total_assets, monthly_outflow)
    overall, s_score, d_score, r_score = health_score(sr, dti, runway)

    return Metrics(
        period_start=min(dated) if dated else None,
        period_end=max(dated) if dated else None,
        months=float(months),
        monthly_income=round(monthly_income, 2),
        monthly_expenses=round(monthly_expenses, 2),
        monthly_debt_payments=round(monthly_debt, 2),
        monthly_investments=round(monthly_investments, 2),
        net_cash_flow=round(net_cash_flow, 2),
        essential_expenses=round(essential / months, 2),
        discretionary_expenses=round(discretionary / months, 2),
        subscription_count=subscription_count,
        subscriptions_monthly=round(subscriptions_monthly, 2),
        savings_rate=round(sr, 4),
        debt_to_income=round(dti, 4),
        total_assets=round(total_assets, 2),
        total_liabilities=round(total_liabilities, 2),
        emergency_runway_months=round(runway, 2) if runway is not None else None,
        health_score=overall,
        savings_score=s_score,
        debt_score=d_score,
        runway_score=r_score,
        expense_breakdown=expense_breakdown,
        monthly_trend=monthly_trend,
    )
