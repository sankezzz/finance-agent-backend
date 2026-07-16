# Agent 3 — Financial Analysis

_The third station. Turns categorized transactions + facts into an auditable
**metrics snapshot** — savings rate, debt ratio, emergency runway, health score,
and the dashboard breakdowns. **Pure math, no LLM.**_

---

## 1. What it does & the design principle

It computes the numbers. **Deliberately no LLM** — for a finance app the metrics
must be:

- **Correct** — `sum()` never miscalculates; LLMs approximate arithmetic.
- **Reproducible** — same data → same score every run (no wobble).
- **Auditable** — every number traces to a formula and its inputs.
- **Testable** — the math is pure functions, unit-tested with known inputs.

The LLM's value (interpreting these numbers into advice) belongs to **Agent 4**,
which reads this snapshot and can only *reason about* the numbers, never invent
them. That grounding is what prevents financial hallucination.

Structure:
- [`core/finance/calculations.py`](../app/core/finance/calculations.py) — **pure**
  functions (`savings_rate`, `debt_to_income`, `emergency_runway`,
  `health_score`, `compute_metrics`). No DB, no LLM, no I/O.
- [`agents/analysis_agent.py`](../app/agents/analysis_agent.py) — **thin** wrapper:
  fetch → `compute_metrics` → save. No arithmetic of its own.

---

## 2. When it runs

Stage 3, after categorization, over the same `run_id`:

```
parse → categorize → ANALYZE → recommend
```

It reads the run's `transactions` (now categorized) + `financial_facts`, plus the
user's declared income as a fallback, and writes one row to `financial_snapshots`.

---

## 3. How it works

```
transactions(run_id) + facts(run_id) + user.declared_income
        └─ compute_metrics()  (pure)
               ├─ normalise everything to MONTHLY over the observed period
               ├─ reconcile income, classify each category
               ├─ savings rate · debt-to-income · runway · health score
               └─ dashboard extras (essential/discretionary, subs, trend)
        └─ save_snapshot(run_id)   (one row per run, upsert)
```

### Money definitions (all MONTHLY)
| Metric | Definition |
|---|---|
| `monthly_income` | **net salary fact** → Income-category credits ÷ months → declared onboarding income (first available wins — no double-counting salary) |
| `monthly_expenses` | consumption debits ÷ months |
| `monthly_debt_payments` | EMI_Loan debits ÷ months (fallback: loan facts' `emi`) |
| `monthly_investments` | Investment debits ÷ months — **counted as savings, not spend** |
| `net_cash_flow` | income − expenses − debt_payments (= amount saved) |

### Which category counts where
- **Consumption** (expenses): Food, Rent, Utilities, Shopping, Travel, Entertainment, Health, Other
- **Debt**: EMI_Loan
- **Savings**: Investment
- **Excluded from spend ratios**: Transfer, ATM cash, credit-card bill payments (money moving, not consumed), and Income (that's the income side)

### Ratios & score
```
savings_rate      = (income − expenses − debt) / income
debt_to_income    = debt_payments / income
emergency_runway  = total_assets / (expenses + debt_payments)   # months
```

`total_assets` / `total_liabilities` come from the `financial_facts` (asset /
liability rows the parser extracted).

---

## 4. Health score (0–100, transparent)

A weighted blend of three sub-scores, each 0–100 — all constants documented in
[`calculations.py`](../app/core/finance/calculations.py):

| Sub-score | Full marks at | Zero at |
|---|---|---|
| `savings_score` | savings rate ≥ 20% | ≤ 0% |
| `debt_score` | DTI = 0% | DTI ≥ 40% |
| `runway_score` | runway ≥ 6 months | 0 months |

```
health_score = 0.40·savings_score + 0.30·debt_score + 0.30·runway_score
```

Sub-scores are stored too, so the recommendation agent / dashboard can explain
*why* the score is what it is.

---

## 5. Dashboard fields

Beyond the core metrics, the snapshot also carries (all pure/deterministic):

| Field | Powers |
|---|---|
| `essential_expenses` / `discretionary_expenses` | needs-vs-wants split (essential = Rent/Utilities/Health/Food) |
| `subscription_count` / `subscriptions_monthly` | "Recurring Subscriptions" panel (from `is_subscription`) |
| `expense_breakdown` | "Top Expense Categories" (category → monthly ₹) |
| `monthly_trend` | "Spending Trends" chart (per-month expenses/debt/investments) |

Debt and asset *lists* aren't duplicated here — the dashboard endpoint composes
those directly from `financial_facts`.

---

## 6. Files

| File | Role |
|------|------|
| [`app/core/finance/calculations.py`](../app/core/finance/calculations.py) | Pure math: ratios, health score, `compute_metrics`. |
| [`app/agents/analysis_agent.py`](../app/agents/analysis_agent.py) | Thin agent: fetch → compute → save. |
| [`app/models/financial.py`](../app/models/financial.py) | `Metrics`, `Snapshot`, `MonthPoint`. |
| [`app/services/financial_service.py`](../app/services/financial_service.py) | `save_snapshot` / `get_snapshot`. |
| [`db/schema.sql`](../db/schema.sql) | `financial_snapshots` table (one per run). |

---

## 7. How to test

Runs the analysis over an already parsed+categorized run and prints the full
snapshot (income/expenses split, ratios, health score with sub-scores, expense
breakdown, spending trend):

```bash
python tests/test_analysis.py <run_id>
```

See [`tests/test_analysis.py`](../tests/test_analysis.py). The core math is also
unit-testable directly — `compute_metrics` takes plain model lists and returns a
`Metrics` object with no DB involved.

---

## 8. Current limitations

- **Multi-period normalisation**: months = the union of calendar months seen
  across *all* documents. If a loan statement carries earlier dates than the
  bank statement, spending gets divided by a larger span and is slightly
  understated. A more precise version would normalise per source/period.
- **Liquid assets = total assets**: runway treats all assets (incl. FDs, stocks)
  as available. FDs/equity aren't instantly liquid, so runway is optimistic.
- **ATM cash is unattributed**: withdrawals are Transfer, so cash later spent
  isn't counted in any spend category — can understate real expenses.
- **Essential/discretionary is a fixed heuristic** (Food treated as essential);
  it doesn't distinguish groceries from dining.
- **Health-score weights are opinionated** (40/30/30) — reasonable defaults, but
  not personalised to the user's life stage or dependents.
