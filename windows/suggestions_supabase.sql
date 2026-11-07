-- DID Improvement Suggestions — execute in YOUR Supabase project's SQL editor.
-- 1. Create one normal Supabase Auth user for the owner (do not share its password).
-- 2. Replace 00000000-0000-0000-0000-000000000000 below with that user's UUID.
-- 3. Never distribute a service-role/secret key. The client needs only sb_publishable_... .
-- This SQL has not been deployed or security-tested against a live project.

create table if not exists public.improvement_suggestions (
    id uuid primary key,
    created_at timestamptz not null default now(),
    author text not null check (char_length(author) between 1 and 100),
    proposal jsonb not null check (
        jsonb_typeof(proposal) = 'object'
        and jsonb_typeof(proposal -> 'changes') = 'array'
        and jsonb_array_length(proposal -> 'changes') between 1 and 1000
        and jsonb_typeof(proposal -> 'draft') = 'object'
        and octet_length(proposal::text) <= 145000
    ),
    status text not null default 'pending' check (status in ('pending','approved','rejected'))
);

create index if not exists did_suggestions_status_created_idx
    on public.improvement_suggestions (status, created_at desc);

alter table public.improvement_suggestions enable row level security;
revoke all on public.improvement_suggestions from public, anon, authenticated;
-- Anonymous users can submit ONLY the designated columns; cannot provide status/time.
grant insert (id, author, proposal) on public.improvement_suggestions to anon;
-- Only a signed-in owner can read the inbox and update the status column.
grant select on public.improvement_suggestions to authenticated;
grant update (status) on public.improvement_suggestions to authenticated;

drop policy if exists "DID public submit pending only" on public.improvement_suggestions;
create policy "DID public submit pending only" on public.improvement_suggestions
for insert to anon with check (status = 'pending');

drop policy if exists "DID owner reads suggestions" on public.improvement_suggestions;
create policy "DID owner reads suggestions" on public.improvement_suggestions
for select to authenticated
using ((select auth.uid()) = '0d56efe1-3c4c-4241-bde9-5065177d6e61'::uuid);

drop policy if exists "DID owner reviews pending" on public.improvement_suggestions;
create policy "DID owner reviews pending" on public.improvement_suggestions
for update to authenticated
using (status = 'pending' and (select auth.uid()) = '0d56efe1-3c4c-4241-bde9-5065177d6e61'::uuid)
with check (status in ('approved','rejected') and (select auth.uid()) = '0d56efe1-3c4c-4241-bde9-5065177d6e61'::uuid);

-- Production hardening required: server-side abuse prevention (e.g. CAPTCHA or
-- rate-limited Edge Function). Client-side cooldown alone cannot stop spam.
-- Verify allow/deny for anon, unrelated auth users and owner with Supabase RLS tests.
