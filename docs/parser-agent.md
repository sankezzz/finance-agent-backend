# Agent 1 — Document Parser

_The first station in the pipeline. Turns raw uploaded files into structured,
run-scoped financial data. This is the only place we read the raw documents and
the first place we call the LLM._

---

## 1. What it does

For every document a user has uploaded, the parser:

```
download file → extract text → mask PII → LLM parse → persist → mark parsed
```

It produces **two different shapes of data**, depending on the document:

- **`transactions`** — ledger line-items (from bank & credit-card statements)
- **`financial_facts`** — point-in-time figures (salary, loan outstanding,
  investment/FD value, credit-card outstanding)

This split is deliberate: a coffee purchase (dated, has a direction/merchant) and
a loan's "₹25L outstanding" (a single figure with an interest rate) don't belong
in the same table. Both are kept — nothing extracted is thrown away.

---

## 2. When it runs

The parser has **no endpoint of its own.** It runs *inside* the pipeline, as the
first stage, triggered by the pipeline endpoint:

```
POST /documents         (upload one or more files; status = "uploaded")
POST /pipeline/runs      → creates a run_id, starts the pipeline in the background
   └─ Stage 1: ParserAgent.run(ctx)   ← this agent
   └─ Stage 2..4: categorizer → analysis → recommendation (later)
GET  /pipeline/runs/{id} → poll; "parse" stage flips pending → running → done
```

**All of a user's uploaded documents are processed in ONE run** — the run is the
unit that produces a single, unified dataset. Every transaction and fact from
that run carries the same `run_id`, so re-running never duplicates data.

---

## 3. How it works, step by step

Per document ([`parser_agent.py`](../app/agents/parser_agent.py)):

| Step | What happens | Where |
|------|--------------|-------|
| 1. Download | Fetch raw bytes from Supabase Storage by `storage_path`. | `document_service.download_document` |
| 2. Extract text | PDF → `pypdf`, CSV → `csv`, Excel → `openpyxl`. | `_extract_text` |
| 3. **Mask PII** | Account/card numbers → last-4 only; PAN/email removed. **Before** the LLM. | `core.security.scrub_text` |
| 4. LLM parse | Per-doc-type prompt → Groq → validated `ParsedDocument` (via `instructor`). | `_llm_parse` |
| 5. Persist | Map to `TransactionCreate` / `FinancialFactCreate` (add run_id, user_id, document_id) and insert. | `_persist` |
| 6. Mark | Document status → `parsed`. | `document_service.set_status` |

### Failure handling
Each document is processed in isolation. If one file fails (unreadable, bad
format), it's marked `failed` and the others continue. The **stage** only fails
if *every* document fails — that way a systemic problem (e.g. a bad API key)
still surfaces as a failed run, but one corrupt file doesn't sink the batch.

---

## 4. Per-document-type behaviour

Each type gets its own prompt ([`llm/prompts/parser.py`](../app/llm/prompts/parser.py))
and produces different output:

| Document type | Produces | Example rows |
|---|---|---|
| `bank_statement` | `transactions` (+ optional savings balance fact) | credit/debit line items |
| `credit_card_statement` | `transactions` + `cc_outstanding` fact | purchases, payments, amount due |
| `salary_slip` | `facts` (income) | `salary` net pay, `gross_salary`; deductions in `meta` |
| `loan_statement` | `facts` (liability) + EMI transactions | `home_loan` outstanding, `meta.emi`, `meta.interest_rate` |
| `investment_statement` | `facts` (asset) | one per holding: `mutual_fund` / `fd` / … value |

---

## 5. Where the data lands

### `transactions` ([schema](../db/schema.sql))
Ledger line-items. `category` and the `is_recurring` / `is_subscription` flags
are **left null by the parser** — the categorizer (Agent 2) fills them next.

Key columns: `run_id`, `user_id`, `document_id`, `txn_date`, `description`,
`amount`, `direction` (credit/debit), `merchant`, `metadata`.

### `financial_facts` ([schema](../db/schema.sql))
Point-in-time figures feeding Income / Assets / Liabilities.

Key columns: `run_id`, `user_id`, `document_id`, `kind`
(income/expense/asset/liability), `subtype` (free text: `salary`, `home_loan`,
`mutual_fund`, `fd`, `cc_outstanding`…), `amount`, `metadata`.

Both are **run-scoped** (`run_id`), which is what makes re-runs clean and keeps
each run's dataset independent.

---

## 6. Security — the LLM boundary

Masking happens in [`core/security.py`](../app/core/security.py) and runs on the
extracted text **before** it's ever put in a prompt:

```
A/C 123456789012  →  A/C XXXXXXXX9012
card 4532 1122 3344 5566  →  card XXXXXXXXXXXX5566
PAN ABCDE1234F  →  PAN [PAN]
me@example.com  →  [EMAIL]
paid 12,500.00  →  paid 12,500.00      (amounts preserved)
```

Last-4 is kept so the model can still associate a row with an account, but the
full number never leaves our process. Amounts are untouched so extraction stays
accurate.

---

## 7. Files

| File | Role |
|------|------|
| [`app/agents/parser_agent.py`](../app/agents/parser_agent.py) | The agent (extract → mask → LLM → persist). |
| [`app/models/parser.py`](../app/models/parser.py) | LLM output contract (`ParsedDocument`, `ExtractedTransaction`, `ExtractedFact`). |
| [`app/models/transaction.py`](../app/models/transaction.py) | `Transaction` / `TransactionCreate`. |
| [`app/models/fact.py`](../app/models/fact.py) | `FinancialFact` / `FinancialFactCreate`. |
| [`app/llm/prompts/parser.py`](../app/llm/prompts/parser.py) | Per-doc-type prompts + system prompt. |
| [`app/llm/client.py`](../app/llm/client.py) | `get_structured_llm()` — Groq wrapped with `instructor`. |
| [`app/core/security.py`](../app/core/security.py) | PII masking. |
| [`app/services/transaction_service.py`](../app/services/transaction_service.py) | Transaction CRUD. |
| [`app/services/fact_service.py`](../app/services/fact_service.py) | Fact CRUD. |
| [`app/services/document_service.py`](../app/services/document_service.py) | Download + status helpers. |

---

## 8. How to test

Two end-to-end scripts drive the real endpoints (in-process `TestClient`) and
print every stage — extracted text → masked text → Groq output → saved rows.

**Single document** — deepest per-stage view:
```bash
# Prereq: run db/schema.sql in Supabase; set .env (SUPABASE_*, GROQ_API_KEY)
python tests/test_parser_flow.py path/to/bank_statement.pdf --doc-type bank_statement
```

**Multiple documents in one run** — uploads every file in a folder (doc_type
inferred from filename), parses them under a single run_id, times each Groq
call, and surfaces 429 rate-limits:
```bash
python tests/test_parser_multi.py dummy_data/
python tests/test_parser_multi.py dummy_data/ --verbose   # full Groq JSON per doc
python tests/test_parser_multi.py dummy_data/ --delay 5   # space calls to dodge TPM limits
```

See [`tests/test_parser_flow.py`](../tests/test_parser_flow.py) and
[`tests/test_parser_multi.py`](../tests/test_parser_multi.py).

---

## 9. Current limitations

- **Images**: `.png/.jpg` upload is accepted but parsing raises "OCR not enabled
  yet" (that doc is marked `failed`, others continue). OCR is a later add.
- **Model**: defaults to `llama-4-scout-17b` (chosen for Groq's TPM/TPD free-tier
  limits — reasoning models truncate the tool-call), overridable via
  `PARSER_GROQ_MODEL` in `.env`. Output is capped at `GROQ_MAX_TOKENS` (8000).
- **Very large statements**: a document with an extreme number of transactions
  can approach the output-token cap. If extraction ever truncates
  (`tool_use_failed`), the fix is to chunk the document by page and parse in
  pieces — not yet implemented.
- **Categorization**: the parser does not categorize — `category` stays null
  until Agent 2 runs.
- **No de-dup across documents**: if the same transaction appears in two uploaded
  files, it's stored twice. Cross-document de-dup is a possible later refinement.
