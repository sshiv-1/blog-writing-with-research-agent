-- =============================================================================
-- SAGE Supabase Schema: Jobs, Slide Jobs, User API Keys & Artifact Storage
-- Phase 3b: Persistence + Auth (Idempotent)
-- =============================================================================

-- Enable UUID extension if not already present
create extension if not exists "uuid-ossp";

-- ---------------------------------------------------------------------------
-- 1. Table: jobs
-- ---------------------------------------------------------------------------
create table if not exists public.jobs (
    id uuid primary key,
    user_id uuid references auth.users(id) on delete cascade,
    topic text,
    status text not null default 'queued',
    stage text not null default 'queued',
    progress int not null default 0,
    params jsonb not null default '{}'::jsonb,
    state jsonb not null default '{}'::jsonb,
    error text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Index on (user_id, created_at desc) for efficient user job history queries
create index if not exists idx_jobs_user_created
    on public.jobs(user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 2. Table: slide_jobs
-- ---------------------------------------------------------------------------
create table if not exists public.slide_jobs (
    id uuid primary key references public.jobs(id) on delete cascade,
    user_id uuid references auth.users(id) on delete cascade,
    status text not null default 'queued',
    progress int not null default 0,
    current_step text not null default 'queued',
    error text,
    result jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

-- Index on (user_id, created_at desc) for user slide jobs
create index if not exists idx_slide_jobs_user_created
    on public.slide_jobs(user_id, created_at desc);

-- ---------------------------------------------------------------------------
-- 3. Table: user_api_keys
-- ---------------------------------------------------------------------------
create table if not exists public.user_api_keys (
    user_id uuid not null references auth.users(id) on delete cascade,
    provider text not null,
    encrypted_key text not null,
    key_last4 text not null,
    created_at timestamptz not null default now(),
    primary key (user_id, provider)
);

-- ---------------------------------------------------------------------------
-- 4. Row Level Security (RLS)
-- ---------------------------------------------------------------------------
alter table public.jobs enable row level security;
alter table public.slide_jobs enable row level security;
alter table public.user_api_keys enable row level security;

-- Policy: Authenticated users can SELECT only their own jobs
drop policy if exists "Authenticated users select own jobs" on public.jobs;
create policy "Authenticated users select own jobs"
    on public.jobs
    for select
    to authenticated
    using (auth.uid() = user_id);

-- Policy: Authenticated users can SELECT only their own slide jobs
drop policy if exists "Authenticated users select own slide jobs" on public.slide_jobs;
create policy "Authenticated users select own slide jobs"
    on public.slide_jobs
    for select
    to authenticated
    using (auth.uid() = user_id);

-- Note: NO policies for authenticated on user_api_keys.
-- Access is strictly reserved for the backend service role.

-- ---------------------------------------------------------------------------
-- 5. Storage: artifacts bucket (Private)
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('artifacts', 'artifacts', false)
on conflict (id) do update set public = false;

-- Note: NO storage.objects policies for authenticated users.
-- The backend streams artifacts via service role after validating ownership.
