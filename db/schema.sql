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
