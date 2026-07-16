# Agent 2 — Categorizer

_The second station. Takes the raw transactions Agent 1 produced and adds
meaning: what each one is for (`category`), and whether it repeats
(`is_recurring` / `is_subscription`). Hybrid: rules first, LLM only for the
long tail._

---

## 1. What it does

Reads this run's `transactions` and fills the three fields the parser left
blank:

| Field | Meaning |
|---|---|
| `category` | What the money was for (Food, Rent, Investment…) |
| `is_recurring` | Repeats on a regular cadence (rent, EMI, salary, subscriptions) |
| `is_subscription` | A recurring auto-charge to a service (Netflix, Spotify…) — a subset of recurring |

It does **not** touch `financial_facts` — salary/loans/investments already carry
`kind`/`subtype` from the parser. Only transactions get categorized.

---

## 2. When it runs

Stage 2 of the pipeline, right after the parser, over the same `run_id`:

```
parse → CATEGORIZE → analyze → recommend
```

It reads the transactions the parser wrote (`transaction_service.list_transactions(run_id)`)
and writes the three fields back to those same rows.

---

## 3. How it works

```
load transactions(run_id)
  ├─ categorize each:
  │     rules pass (keyword → category, word-boundary match)   ← free, deterministic
  │     credits: salary → Income, else Transfer
  │     unknown debits → deduped → ONE batched LLM call        ← only the long tail
  │     LLM fails? → default to Other (never fails the run)
  ├─ recurring/subscription: group by merchant, apply heuristics (no LLM)
  └─ bulk-update rows, grouped by (category, recurring, subscription)
```

### Why hybrid (rules + LLM)
A rule is just a keyword lookup: *"if the description contains this known
merchant, it's this category."* A handful of big merchants (Swiggy, Netflix,
Amazon, rent, EMI…) cover most transactions for **zero tokens and identical
results every run**. Only genuinely unknown merchants (`UPI-PQR ENTERPRISES`)
fall through to the LLM. This keeps categorization cheap, fast, and mostly
deterministic — which matters for a finance app (category totals shouldn't
wobble between two runs of the same data).

### The LLM fallback — one batched call, JSON mode
- Unknown **debit** merchants are **deduped** (5 Swiggy orders → one decision)
  and sent in a **single** call, not one-per-transaction.
- It uses **JSON mode**, not tool-calling. The small fallback model
  (`llama-3.1-8b-instant`) reliably mangles the function-call wrapper
  (`/function` instead of `</function>`) → Groq `tool_use_failed`. JSON mode
  removes the wrapper entirely; the model just returns a JSON object that
  `instructor` validates against the category enum. (See
  [`llm/client.py`](../app/llm/client.py) `get_structured_llm(mode="json")`.)
- If the fallback still errors, unknowns default to `Other` — a fallback
  hiccup never fails the whole run.

---

## 4. Category taxonomy

A **fixed** enum ([`models/transaction.py`](../app/models/transaction.py) →
`TransactionCategory`) so the dashboard can aggregate cleanly:

```
Food · Rent · Utilities · Shopping · Travel · Entertainment ·
EMI_Loan · Health · Investment · Income · Transfer · Other
```

Two deliberate choices:
- **Subscriptions is NOT a category** — it's the `is_subscription` flag. Netflix
  is genuinely *Entertainment* that happens to be a subscription. Category =
  "what it's for"; the flag = "is it a recurring auto-charge." No overlap.
- **`Investment` is its own category** — a SIP / mutual-fund debit is money
  *leaving* the account, but it's **savings, not spending**. Without this
  category the LLM guessed "Income" for `GROWW…STARMF-SIP`, inflating income and
  hiding savings. Agent 3 treats `Investment` outflows as savings.

---

## 5. Rules & word-boundary matching

Rules live in [`categorizer_agent.py`](../app/agents/categorizer_agent.py) as an
ordered `_RULES` list (first match wins; Investment/EMI checked before generic
Shopping). Matching is done on **word boundaries**, not raw substring:

```python
# "ajio" must NOT match the "jio" (Reliance Jio) utility keyword:
re.search(rf"\b{re.escape(kw)}\b", text)
```

This fixed a real bug where `UPI-AJIO` (Shopping) matched `jio` (Utilities)
because "a**jio**" contains "jio". Word boundaries keep real Jio → Utilities and
AJIO → Shopping.

Credits are handled separately: `salary`/`payroll` → `Income`, everything else
→ `Transfer` (safer than guessing income). Only unknown **debits** reach the LLM.

---

## 6. Recurring & subscription detection (no LLM)

Deterministic, from grouping transactions by normalized merchant:

- **`is_recurring`** if the merchant spans **2+ calendar months**, appears **3+
  times**, or is a subscription.
- **`is_subscription`** if the merchant matches a subscription keyword list
  (Netflix, Spotify, gym, Google One, Adobe…). Every subscription is recurring;
  not every recurring charge is a subscription (rent recurs but isn't one).

The "recurring subscriptions" dashboard panel is just `where is_subscription = true`.

---

## 7. Files

| File | Role |
|------|------|
| [`app/agents/categorizer_agent.py`](../app/agents/categorizer_agent.py) | The agent: rules, LLM fallback, recurring detection. |
| [`app/models/transaction.py`](../app/models/transaction.py) | `TransactionCategory` enum. |
| [`app/models/categorizer.py`](../app/models/categorizer.py) | LLM batch contract (`CategoryBatch`). |
| [`app/llm/prompts/categorizer.py`](../app/llm/prompts/categorizer.py) | Fallback prompt + system prompt. |
| [`app/llm/client.py`](../app/llm/client.py) | `get_structured_llm(mode)` — tools vs JSON. |
| [`app/services/transaction_service.py`](../app/services/transaction_service.py) | `apply_categorizations()` — grouped bulk updates. |
| [`app/config.py`](../app/config.py) | `CATEGORIZER_GROQ_MODEL` (llama-3.1-8b-instant). |

---

## 8. How to test

Runs the categorizer over an already-parsed run (cheap — reuses transactions,
only the fallback call fires) and prints the category breakdown, recurring
count, and detected subscriptions:

```bash
python tests/test_categorizer.py <run_id>
```

See [`tests/test_categorizer.py`](../tests/test_categorizer.py). It's idempotent —
re-running re-categorizes and bulk-updates the same rows.

---

## 9. Current limitations

- **ATM withdrawals → Transfer**: we can't know what the withdrawn cash was
  later spent on, so it's not attributed to a spend category.
- **Rules are India-centric** (Swiggy, Groww, MSEDCL…). Unknown/foreign
  merchants rely entirely on the LLM fallback; extend `_RULES` as new common
  merchants appear.
- **Recurring is weak on single-month data**: the 2+ month signal needs a
  statement spanning multiple months to fire (3+ occurrences and the
  subscription keyword list still work within one month).
- **No cross-run learning**: an LLM decision for an unknown merchant isn't
  cached into the rules table for next time (a possible later optimization).
