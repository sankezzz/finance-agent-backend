# Personal Finance Copilot — API Reference

Complete contract for the frontend. Pairs with `frontend-brief.md` (the product
& design vision); this is the data.

---

## Overview

- **Base URL** (dev): `http://127.0.0.1:8000`
- **Auth**: none (MVP). Onboarding returns a `user_id`; store it in
  `localStorage` and pass it where each endpoint requires it. No tokens/cookies.
- **Content types**: JSON everywhere, **except** document upload which is
  `multipart/form-data`.
- **Currency**: all money values are **INR (₹)**, plain numbers (no formatting).
- **Errors**: FastAPI style — non-2xx responses look like:
  ```json
  { "detail": "User not found" }
  ```
  Validation errors (422) have `detail` as an array of field errors.
- **CORS**: open (`*`) in dev.

### Typical flow
```
POST /onboarding                     → user_id
POST /documents        (once per file, multipart)
POST /pipeline/runs    { user_id }   → run_id   (202; pipeline runs in background)
GET  /pipeline/runs/{run_id}         → poll until status == "done"
GET  /dashboard/{user_id}            → the whole dashboard payload
```

---

## Endpoints

### `GET /health`
Liveness check.
```json
200 → { "status": "ok" }
```

---

### `POST /onboarding`
Create a user profile. Returns the stored user (with generated `id`).

**Request body** (`application/json`):
```json
{
  "name": "Aarav Sharma",
  "age": 30,
  "monthly_income": 97500,          // optional, may be null
  "dependents": 0,
  "existing_loans": [
    { "type": "auto", "outstanding": 250000, "monthly_emi": 5893 }
  ],
  "financial_goals": [
    { "name": "Car", "target_amount": 1500000, "target_date": "2028-01-01" }
  ]
}
```
`existing_loans` and `financial_goals` default to `[]`. `monthly_income`,
`target_date` may be omitted/null.

**Response** `201`: a [User](#user).

**Errors**: `422` invalid body.

---

### `GET /onboarding/{user_id}`
Fetch a user profile.

**Response** `200`: a [User](#user). **`404`** if not found.

---

### `POST /documents`
Upload ONE financial document. Call once per file. Stored with status
`uploaded`; nothing is processed yet.

**Request** (`multipart/form-data`):
| Field | Type | Notes |
|---|---|---|
| `user_id` | text | the onboarded user |
| `doc_type` | text | one of [DocumentType](#documenttype) |
| `file` | file | `.pdf .csv .xls .xlsx .png .jpg .jpeg` |

**Response** `201`: a [Document](#document).

**Errors**: `404` user not found · `400` unsupported file type · `422` missing field.

---

### `GET /documents?user_id={user_id}`
List a user's uploaded documents (oldest first).

**Response** `200`: `Document[]`.

---

### `POST /pipeline/runs`
Trigger the analysis pipeline over **all** of the user's uploaded documents.
Returns immediately; the 4 agents run in the background.

**Request body**:
```json
{ "user_id": "fd87f41c-..." }
```

**Response** `202`: a [Run](#run) (freshly created — `status: "pending"`,
all stages `pending`). **`404`** if user not found.

> The returned run is the *starting* state. Poll the next endpoint to watch it
> progress. Do **not** expect agent output here — only status.

---

### `GET /pipeline/runs/{run_id}`
Poll a run's status. Call on a timer (~1s) from the processing screen.

**Response** `200`: a [Run](#run). **`404`** if not found.

Stop polling when `status` is `"done"` or `"failed"`. This endpoint returns
**status only** — the actual results come from `/dashboard`.

---

### `GET /dashboard/{user_id}`
The composed dashboard from the user's **latest analysis**. Call this once the
run is `done`.

**Response** `200`: a [DashboardResponse](#dashboardresponse).

**Errors**: `404` user not found · `404` `"No analysis yet…"` if the user has no
completed snapshot.

---

## Data models

### User
```jsonc
{
  "id": "uuid",
  "name": "string",
  "age": 30,
  "monthly_income": 97500,        // number | null
  "dependents": 0,
  "existing_loans": [ Loan ],
  "financial_goals": [ FinancialGoal ],
  "created_at": "2026-07-16T09:00:00Z"
}
```

**Loan**
```jsonc
{ "type": "auto", "outstanding": 250000, "monthly_emi": 5893 }
// type ∈ LoanType
```

**FinancialGoal**
```jsonc
{ "name": "Car", "target_amount": 1500000, "target_date": "2028-01-01" }
// target_date: "YYYY-MM-DD" | null
```

---

### Document
```jsonc
{
  "id": "uuid",
  "user_id": "uuid",
  "doc_type": "bank_statement",   // DocumentType
  "filename": "statement.pdf",
  "storage_path": "user_id/doc_id/statement.pdf",
  "content_type": "application/pdf",  // may be null
  "size_bytes": 183623,               // may be null
  "status": "uploaded",               // DocumentStatus
  "created_at": "2026-07-16T09:07:40Z",
  "url": null                          // reserved; not currently populated
}
```

---

### Run
```jsonc
{
  "id": "uuid",
  "user_id": "uuid",
  "status": "running",             // RunStatus
  "current_stage": "analyze",      // Stage | null
  "stages": [
    { "stage": "parse",      "status": "done",    "error": null },
    { "stage": "categorize", "status": "done",    "error": null },
    { "stage": "analyze",    "status": "running", "error": null },
    { "stage": "recommend",  "status": "pending", "error": null }
  ],
  "error": null,                   // set if the run failed
  "created_at": "2026-07-16T09:00:00Z",
  "updated_at": "2026-07-16T09:00:05Z"
}
```
`stages` is always the 4 stages in order — render it directly as the progress
checklist.

---

### DashboardResponse
```jsonc
{
  "user": User,
  "run_id": "uuid",
  "run_status": "done",
  "generated_at": "2026-07-16T09:00:10Z",

  "metrics": Snapshot,

  "recommendations_summary": "You save well, but your emergency fund is thin.",
  "recommendations": [ Recommendation ],

  "assets":      [ FinancialFact ],   // kind == "asset"
  "liabilities": [ FinancialFact ],   // kind == "liability"
  "subscriptions": [ SubscriptionItem ],

  "persona": null                     // reserved for the future persona feature
}
```

---

### Snapshot (the metrics)
All money values are **monthly** unless noted. Percentages are **fractions**
(`0.42` = 42%).
```jsonc
{
  "period_start": "2025-04-01",       // date | null
  "period_end":   "2025-06-30",       // date | null
  "months": 3,

  "monthly_income": 97500,
  "monthly_expenses": 29527,          // consumption only
  "essential_expenses": 17600,        // Rent/Utilities/Health/Food
  "discretionary_expenses": 11927,    // Shopping/Travel/Entertainment/Other
  "monthly_debt_payments": 5893,
  "monthly_investments": 9000,        // treated as savings
  "net_cash_flow": 61607,             // income - expenses - debt

  "subscription_count": 4,
  "subscriptions_monthly": 1027,

  "savings_rate": 0.63,               // fraction
  "debt_to_income": 0.06,             // fraction
  "total_assets": 704590,
  "total_liabilities": 129988,
  "emergency_runway_months": 19.9,    // number | null

  "health_score": 84.9,               // 0-100
  "savings_score": 100,               // 0-100
  "debt_score": 85,                   // 0-100
  "runway_score": 84,                 // 0-100

  "expense_breakdown": {              // category → monthly ₹  (donut chart)
    "Rent": 15000, "Shopping": 4346, "Food": 3159
  },
  "monthly_trend": [                  // spending-over-time (line chart)
    { "month": "2025-04", "expenses": 28900, "debt": 5893, "investments": 9000 },
    { "month": "2025-05", "expenses": 31200, "debt": 5893, "investments": 9000 }
  ],

  // also present (DB fields): "id", "run_id", "user_id", "created_at"
}
```

---

### Recommendation
```jsonc
{
  "title": "Build your emergency fund",
  "category": "emergency_fund",       // RecommendationCategory
  "priority": "high",                 // Priority
  "rationale": "Your runway is 2.3 months, below the 6-month target.",
  "action": "Redirect ₹10K/mo from discretionary spend until you reach ₹2.1L."
}
```
Sort/group by `priority` in the UI.

---

### FinancialFact  (assets & liabilities)
```jsonc
{
  "id": "uuid",
  "run_id": "uuid",
  "user_id": "uuid",
  "document_id": "uuid",              // may be null
  "kind": "liability",               // FactKind
  "subtype": "home_loan",            // free text: mutual_fund, fd, salary, cc_outstanding, ...
  "label": "HDFC Home Loan",         // may be null
  "amount": 129988,
  "currency": "INR",
  "metadata": { "emi": 5893, "interest_rate": 8.5 },
  "created_at": "2026-07-16T09:00:08Z"
}
```

### SubscriptionItem
```jsonc
{ "merchant": "NETFLIX", "amount": 649, "category": "Entertainment" }
```

---

## Enums

| Enum | Values |
|---|---|
| **DocumentType** | `bank_statement` · `credit_card_statement` · `salary_slip` · `investment_statement` · `loan_statement` |
| **DocumentStatus** | `uploaded` · `processing` · `parsed` · `failed` |
| **RunStatus** | `pending` · `running` · `done` · `failed` |
| **StageStatus** | `pending` · `running` · `done` · `failed` |
| **Stage** | `parse` · `categorize` · `analyze` · `recommend` |
| **LoanType** | `home` · `personal` · `auto` · `education` · `credit_card` · `other` |
| **TransactionCategory** (in `expense_breakdown` keys / subscription `category`) | `Food` · `Rent` · `Utilities` · `Shopping` · `Travel` · `Entertainment` · `EMI_Loan` · `Health` · `Investment` · `Income` · `Transfer` · `Other` |
| **RecommendationCategory** | `savings` · `debt` · `spending` · `emergency_fund` · `investment` · `income` · `general` |
| **Priority** | `high` · `medium` · `low` |
| **FactKind** | `income` · `expense` · `asset` · `liability` |

---

## Frontend notes

- **Poll** `GET /pipeline/runs/{run_id}` every ~1s while `status ∈ {pending, running}`;
  render `stages` as the agent progress. It carries **no result data** — only status.
- Fetch **`GET /dashboard/{user_id}`** exactly once, after `status == "done"`.
- Percentages (`savings_rate`, `debt_to_income`) are fractions → multiply by 100.
- `emergency_runway_months` and several `*_null` fields can be `null` — guard them.
- `persona` is `null` today; the contract won't change when it ships — just start
  rendering it when it's non-null.
- Document `url` is not populated yet (no in-app file preview); don't depend on it.
```
