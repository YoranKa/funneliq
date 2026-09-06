-- FunnelIQ database schema.
-- Run this once in the Supabase project's SQL Editor (or via the CLI) to
-- create the table that data/funnel_marketing_data.csv gets loaded into.

create table if not exists public.funnel_records (
    id                       bigint generated always as identity primary key,
    ad_budget                integer not null,
    num_leads                integer not null,
    leads_answered           integer not null,
    leads_not_answered       integer not null,
    followup_1               integer not null,
    followup_2               integer not null,
    followup_3               integer not null,
    followup_4               integer not null,
    followup_5               integer not null,
    not_closed               integer not null,
    closed                   integer not null,
    calls_to_closed          integer not null,
    calls_to_not_closed      integer not null,
    customer_acquisition_cost integer not null,
    ltv_months               numeric,
    purchased                boolean not null,
    upsell                   boolean not null,
    cumulative_profit        numeric,
    referred                 boolean not null,
    created_at               timestamptz not null default now()
);

-- The organization-level "Enable automatic RLS" setting already turns this on
-- for new tables, but it's spelled out here too so the schema is correct on
-- its own, on a project that doesn't have that setting.
alter table public.funnel_records enable row level security;

-- Every row is visible to any signed-in Northbound team member - this is an
-- internal company dashboard, not a multi-tenant app, so there is no
-- per-row ownership to check. `to authenticated` (not `auth.role()`, which
-- Supabase has deprecated and which also lets anonymous sign-ins through)
-- is what actually keeps unauthenticated requests out.
create policy "authenticated users can read funnel records"
    on public.funnel_records
    for select
    to authenticated
    using (true);
