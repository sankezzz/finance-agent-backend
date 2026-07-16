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
