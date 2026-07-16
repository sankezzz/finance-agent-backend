# Personal Finance Copilot — Frontend Brief

_A handoff brief for building the frontend. The backend is done; this explains
what it does, the product vision, and the exact look/feel to build. **Detailed
API endpoint docs are provided separately** — this is the idea and the design._

---

## 1. What we're building

A **Personal Finance Copilot**. A user onboards with a few basics, uploads their
financial documents (bank statement, salary slip, credit-card statement, loan
statement, investment statement), and the system analyses everything and builds
a **financial profile** — health score, spending insights, and personalized,
actionable recommendations. Later they can **chat** with an assistant about their
own money.

The magic: a **multi-agent AI pipeline** processes the documents. We want the UI
to make that feel alive — the user should *watch* their data flow through the
agents, then land on a clean, personal dashboard.

---

## 2. The backend, in brief (conceptual — API docs come separately)

Stack: FastAPI + Supabase (Postgres + Storage) + Groq LLMs. No auth for the MVP —
the frontend gets a `user_id` on onboarding and sends it on later requests (store
it in `localStorage`).

**The flow the frontend drives:**

1. **Onboard** — submit name, age, monthly income, dependents, existing loans,
   financial goals → get back a `user_id`.
2. **Upload documents** — one file at a time, each tagged with its type
   (`bank_statement`, `salary_slip`, `credit_card_statement`, `loan_statement`,
   `investment_statement`). Files just get stored (status `uploaded`); nothing
   processes yet.
3. **Trigger a run** — one call kicks off the pipeline over *all* the user's
   uploaded documents. Returns a `run_id` immediately; work happens in the
   background.
4. **Poll the run** — the run reports per-stage progress. This is what powers the
   "watch the agents work" screen (see §5).
5. **Read the profile** — once the run is `done`, fetch the computed dashboard
   data (metrics + recommendations).

**The 4 agents (the pipeline stages), in order:**

| Stage | Agent | What it produces |
|---|---|---|
| `parse` | Document Parser | Extracts transactions + financial facts from the files |
| `categorize` | Categorizer | Labels each transaction (Food, Rent, Investment…) + recurring/subscription flags |
| `analyze` | Financial Analysis | Pure-math metrics: savings rate, debt ratio, emergency runway, **health score** |
| `recommend` | Recommendation | LLM advice grounded in the metrics: summary + prioritized action cards |

**A run's status object (what you poll) looks like:**
```json
{
  "status": "running",              // pending | running | done | failed
  "current_stage": "analyze",
  "stages": [
    { "stage": "parse",      "status": "done" },
    { "stage": "categorize", "status": "done" },
    { "stage": "analyze",    "status": "running" },
    { "stage": "recommend",  "status": "pending" }
  ]
}
```

**The data available for the dashboard (shapes, not the API contract):**
- **Metrics snapshot** — `health_score` (0-100) + `savings_score`/`debt_score`/`runway_score`,
  `monthly_income`, `monthly_expenses` (with `essential`/`discretionary` split),
  `monthly_debt_payments`, `monthly_investments`, `net_cash_flow`, `savings_rate`,
  `debt_to_income`, `emergency_runway_months`, `total_assets`, `total_liabilities`,
  `expense_breakdown` (category → monthly amount), `monthly_trend` (per-month
  spending series), `subscription_count` + `subscriptions_monthly`.
- **Recommendations** — a short `summary` + a list of items, each with `title`,
  `category`, `priority` (high/med/low), `rationale`, `action`.
- Currency is **INR (₹)**.

---

## 3. The vision (read this first)

Minimal, elegant, **black & white only**, with tasteful gradients and subtle
motion. Think a premium fintech landing page, not a busy dashboard. Every screen
should feel calm and confident. The signature moment is the **agent pipeline
animation** — data visibly flowing from one agent to the next as it processes.

The end state the user lands on: a **dashboard built around their persona** — a
generated "financial personality" — with just the essentials (a couple of clean
graphs + the top recommendations), and a prominent **chat button** that takes
them into a personalized conversation about their money.

---

## 4. Design language

- **Palette: two colors — black and white.** Near-black background (`#0A0A0A`)
  or near-white, with a full gray scale between. **No accent colors.** Depth
  comes from grays, subtle gradients, borders, and shadows — not hue.
- **Gradients**: subtle, monochrome (black→gray, white→gray, faint radial glows).
  Use them for the health-score ring, the hero, primary buttons, and card edges.
  Never loud.
- **Components: shadcn/ui** throughout (Radix + Tailwind). Keep to the neutral/
  zinc theme. Cards, buttons, inputs, dialogs, progress, badges, skeletons.
- **Typography**: clean and modern (Geist, which ships with Next.js). Generous
  whitespace. Large, quiet headings.
- **Motion: light and purposeful** (Framer Motion). Fade/slide-in on mount,
  numbers that count up, smooth stage transitions. Nothing bouncy or loud.
- **Feel**: minimal, lots of negative space, one idea per screen. It should look
  expensive precisely *because* it's restrained.

---

## 5. Screens & flow

### 5.1 Onboarding
A single, calm multi-field form (shadcn inputs) — name, age, monthly income,
dependents, existing loans (add-a-row list), financial goals (optional). Submit →
store `user_id` in `localStorage` → go to upload.

### 5.2 Document upload
Drag-and-drop zone. For each file, pick its type (segmented control / select).
Show the uploaded files as a list with type + a status chip. A primary
**"Analyze my finances"** button triggers the run and moves to the processing
screen. (Upload and analyze are deliberately separate — the user uploads
everything, *then* analyzes once.)

### 5.3 Processing screen ⭐ (the signature moment)
This is where the multi-agent pipeline becomes visible. Show the **4 agents as
nodes** connected left-to-right (or top-to-bottom):

```
[ Parse ] → [ Categorize ] → [ Analyze ] → [ Recommend ]
```

Poll the run status (~1s). As each stage moves `pending → running → done`:
- the active node **pulses / glows** (monochrome), a **light pulse travels along
  the connector** to the next node when a stage completes,
- completed nodes get a subtle check, pending nodes stay dim,
- a soft caption narrates ("Reading your statements…", "Understanding your
  spending…", "Crunching the numbers…", "Writing your recommendations…").

Keep it monochrome and gentle — a quiet, confident "the AI is working" feel. When
`status: done`, transition into the dashboard. If `failed`, show a calm retry.

### 5.4 Dashboard / main screen (the payoff)
Built around the user's **persona** (see §6), minimal and focused — *not* a data
dump:

- **Top: the persona** — a generated financial-personality card (e.g. a title
  like "The Steady Builder" + a 1-2 line description + a few trait chips), with
  the **health score** shown as a monochrome radial gauge nearby.
- **Middle: two minimal graphs** — pick the two that matter most:
  1. **Spending trend** (line, from `monthly_trend`)
  2. **Category breakdown** (donut, from `expense_breakdown`)
  Plus a small row of KPI tiles (income, expenses, savings rate, net cash flow).
- **Then: recommendations** — the top 3-4 cards, sorted by priority, each showing
  title + rationale + action. Minimal, scannable.
- **Bottom: a prominent "Chat with your copilot" button** → the personalized
  chat (§6).

Keep it to one clean scroll. Restraint over completeness.

### 5.5 Chat (personalized)
A conversation screen where the user asks about their own money ("How much do I
spend on food?", "Can I afford a ₹15L car?", "How long will my emergency fund
last?"). Responses are **streamed** (token-by-token) for a live feel. The
assistant is grounded in the user's data and persona.

---

## 6. Future features (build the UI to anticipate these)

- **Persona generation** — after the pipeline finishes, generate a human,
  friendly **financial persona/archetype** from the metrics (a title, a short
  narrative, a few traits). It's the emotional hook of the dashboard — it makes
  the numbers feel personal. Design the dashboard's top section around it now,
  even if it starts as a placeholder.
- **Personalized chat** — the chat knows the user's data + persona and answers
  grounded in them (retrieval over their transactions/metrics). Streaming
  responses. This is the "copilot" the whole product is named for.
- Nice-to-haves later: scenario simulation ("what if I save ₹30k/mo?"), goal
  planning progress, export report to PDF.

---

## 7. Practical notes

- **Stack**: Next.js (App Router) + TypeScript + Tailwind + shadcn/ui +
  **TanStack Query** (its `refetchInterval` is ideal for polling the run status) +
  **Recharts** (or Tremor) for the two graphs + **Framer Motion** for the light
  animations.
- **No auth (MVP)**: keep `user_id` in `localStorage`; send it with requests.
- **API docs are provided separately** — wire the screens to those endpoints.
  This brief is the *product + design* intent, not the API contract.
- **Responsive**: works on mobile; the pipeline animation can stack vertically.
- **States**: every screen needs loading (skeletons), empty, and error states —
  keep them as calm and monochrome as the rest.

---

**In one line:** a minimal black-and-white finance copilot where you watch AI
agents process your documents, land on a persona-driven dashboard with just the
essential graphs and recommendations, and tap through to a personalized chat.
