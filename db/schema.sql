-- Personal Finance Copilot — database schema.
-- No ORM/migrations; run these statements in the Supabase SQL editor.
-- Tables are added here as each feature lands.

-- Users / onboarding profile ------------------------------------------------
create table if not exists public.users (
    id              uuid primary key default gen_random_uuid(),
    name            text not null,
    age             int  not null,
    monthly_income  numeric not null,
    dependents      int  not null default 0,
    existing_loans  jsonb not null default '[]'::jsonb,
    financial_goals jsonb not null default '[]'::jsonb,
    created_at      timestamptz not null default now()
);

-- Uploaded documents --------------------------------------------------------
-- Raw file lives in the private "documents" Storage bucket at storage_path;
-- this row is the DB record of it.
create table if not exists public.documents (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references public.users(id) on delete cascade,
    doc_type      text not null,
    filename      text not null,
    storage_path  text not null,
    content_type  text,
    size_bytes    bigint,
    status        text not null default 'uploaded',
    created_at    timestamptz not null default now()
);

create index if not exists documents_user_id_idx on public.documents(user_id);

-- Pipeline runs -------------------------------------------------------------
-- One row per pipeline execution. `stages` is the per-stage progress the
-- frontend polls; status is the overall run state.
create table if not exists public.runs (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references public.users(id) on delete cascade,
    status        text not null default 'pending',
    current_stage text,
    stages        jsonb not null default '[]'::jsonb,
    error         text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create index if not exists runs_user_id_idx on public.runs(user_id);

-- Transactions --------------------------------------------------------------
-- Ledger line-items extracted from bank & credit-card statements. Scoped to a
-- run_id so each run owns its own set (re-running never duplicates). category
-- and the recurring/subscription flags are filled later by the categorizer.
create table if not exists public.transactions (
    id              uuid primary key default gen_random_uuid(),
    run_id          uuid not null references public.runs(id) on delete cascade,
    user_id         uuid not null references public.users(id) on delete cascade,
    document_id     uuid references public.documents(id) on delete set null,
    txn_date        date,
    description     text not null,
    amount          numeric not null,
    direction       text not null check (direction in ('credit', 'debit')),
    currency        text not null default 'INR',
    merchant        text,
    category        text,
    is_recurring    boolean not null default false,
    is_subscription boolean not null default false,
    metadata        jsonb not null default '{}'::jsonb,
    created_at      timestamptz not null default now()
);

create index if not exists transactions_run_id_idx on public.transactions(run_id);
create index if not exists transactions_user_id_idx on public.transactions(user_id);

-- Financial facts -----------------------------------------------------------
-- Point-in-time figures (NOT ledger line-items): salary, loan outstanding,
-- investment/FD value, credit-card outstanding. These feed the Income /
-- Assets / Liabilities sections of the profile. Also run-scoped.
create table if not exists public.financial_facts (
    id           uuid primary key default gen_random_uuid(),
    run_id       uuid not null references public.runs(id) on delete cascade,
    user_id      uuid not null references public.users(id) on delete cascade,
    document_id  uuid references public.documents(id) on delete set null,
    kind         text not null check (kind in ('income', 'expense', 'asset', 'liability')),
    subtype      text not null,
    label        text,
    amount       numeric not null,
    currency     text not null default 'INR',
    metadata     jsonb not null default '{}'::jsonb,
    created_at   timestamptz not null default now()
);

create index if not exists financial_facts_run_id_idx on public.financial_facts(run_id);
create index if not exists financial_facts_user_id_idx on public.financial_facts(user_id);

-- Financial snapshot --------------------------------------------------------
-- One computed metrics row per run (analysis agent output). run_id is unique
-- so re-analysing a run overwrites its snapshot.
create table if not exists public.financial_snapshots (
    id                       uuid primary key default gen_random_uuid(),
    run_id                   uuid not null unique references public.runs(id) on delete cascade,
    user_id                  uuid not null references public.users(id) on delete cascade,
    period_start             date,
    period_end               date,
    months                   numeric not null default 1,
    monthly_income           numeric not null default 0,
    monthly_expenses         numeric not null default 0,
    monthly_debt_payments    numeric not null default 0,
    monthly_investments      numeric not null default 0,
    net_cash_flow            numeric not null default 0,
    essential_expenses       numeric not null default 0,
    discretionary_expenses   numeric not null default 0,
    subscription_count       int not null default 0,
    subscriptions_monthly    numeric not null default 0,
    savings_rate             numeric not null default 0,
    debt_to_income           numeric not null default 0,
    total_assets             numeric not null default 0,
    total_liabilities        numeric not null default 0,
    emergency_runway_months  numeric,
    health_score             numeric not null default 0,
    savings_score            numeric not null default 0,
    debt_score               numeric not null default 0,
    runway_score             numeric not null default 0,
    expense_breakdown        jsonb not null default '{}'::jsonb,
    monthly_trend            jsonb not null default '[]'::jsonb,
    created_at               timestamptz not null default now()
);

create index if not exists financial_snapshots_user_id_idx on public.financial_snapshots(user_id);

-- Recommendations -----------------------------------------------------------
-- One recommendation set per run (recommendation agent output): a short
-- summary plus a prioritized list of items stored as jsonb.
create table if not exists public.recommendations (
    id          uuid primary key default gen_random_uuid(),
    run_id      uuid not null unique references public.runs(id) on delete cascade,
    user_id     uuid not null references public.users(id) on delete cascade,
    summary     text not null default '',
    items       jsonb not null default '[]'::jsonb,
    created_at  timestamptz not null default now()
);

create index if not exists recommendations_user_id_idx on public.recommendations(user_id);
