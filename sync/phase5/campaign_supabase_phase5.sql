-- DID Character Sheet — Phase 5
-- Session Mode: start/end sessions, archived snapshots, session-scoped rolls,
-- and player-controlled roll sharing during active sessions.
--
-- Run this whole file in the SAME Supabase project after Phase 4.
-- Safe to run more than once.

begin;

create table if not exists public.campaign_sessions (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    session_number integer not null,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    started_by_user_id uuid not null default auth.uid() references auth.users(id) on delete restrict,
    check (session_number >= 1),
    check (ended_at is null or ended_at >= started_at),
    unique (campaign_id, session_number)
);

create unique index if not exists did_one_active_session_per_campaign
    on public.campaign_sessions(campaign_id)
    where ended_at is null;

create index if not exists did_campaign_sessions_campaign_time_idx
    on public.campaign_sessions(campaign_id, started_at desc);

create table if not exists public.session_snapshots (
    id uuid primary key default gen_random_uuid(),
    session_id uuid not null references public.campaign_sessions(id) on delete cascade,
    campaign_character_id uuid not null references public.campaign_characters(id) on delete cascade,
    snapshot_kind text not null check (snapshot_kind in ('start', 'end')),
    captured_at timestamptz not null default now(),
    state jsonb not null,
    check (jsonb_typeof(state) = 'object'),
    unique (session_id, campaign_character_id, snapshot_kind)
);

create index if not exists did_session_snapshots_session_idx
    on public.session_snapshots(session_id, snapshot_kind, captured_at);

alter table public.campaign_rolls
add column if not exists session_id uuid references public.campaign_sessions(id) on delete set null;

create index if not exists did_campaign_rolls_session_time_idx
    on public.campaign_rolls(session_id, rolled_at desc);

alter table public.campaign_characters
add column if not exists share_session_rolls boolean not null default true;

create or replace function private.did_active_session_id(
    p_campaign_id uuid
)
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
    select s.id
    from public.campaign_sessions s
    where s.campaign_id = p_campaign_id
      and s.ended_at is null
    order by s.started_at desc
    limit 1;
$$;

revoke all on function private.did_active_session_id(uuid) from public, anon;
grant execute on function private.did_active_session_id(uuid) to authenticated;

create or replace function private.did_capture_session_snapshots(
    p_session_id uuid,
    p_snapshot_kind text
)
returns integer
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    target_campaign_id uuid;
    affected_count integer := 0;
begin
    if p_snapshot_kind not in ('start', 'end') then
        raise exception 'Invalid snapshot kind';
    end if;

    select s.campaign_id
      into target_campaign_id
      from public.campaign_sessions s
     where s.id = p_session_id;

    if target_campaign_id is null then
        raise exception 'Session not found';
    end if;

    insert into public.session_snapshots(
        session_id,
        campaign_character_id,
        snapshot_kind,
        captured_at,
        state
    )
    select
        p_session_id,
        c.id,
        p_snapshot_kind,
        now(),
        st.state
    from public.campaign_characters c
    join public.character_state st
      on st.campaign_character_id = c.id
    where c.campaign_id = target_campaign_id
      and c.active = true
    on conflict (session_id, campaign_character_id, snapshot_kind)
    do update set
        captured_at = excluded.captured_at,
        state = excluded.state;

    get diagnostics affected_count = row_count;
    return affected_count;
end;
$$;

revoke all on function private.did_capture_session_snapshots(uuid, text)
from public, anon, authenticated;

create or replace function private.did_start_session_impl(
    p_campaign_id uuid
)
returns table (
    id uuid,
    campaign_id uuid,
    session_number integer,
    started_at timestamptz,
    ended_at timestamptz,
    snapshot_count integer
)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
    next_number integer;
    new_session public.campaign_sessions%rowtype;
    captured integer := 0;
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    if not private.did_is_campaign_dm(p_campaign_id, current_user_id) then
        raise exception 'Only the campaign DM can start a session';
    end if;

    if exists (
        select 1 from public.campaign_sessions s
        where s.campaign_id = p_campaign_id
          and s.ended_at is null
    ) then
        raise exception 'This campaign already has an active session';
    end if;

    select coalesce(max(s.session_number), 0) + 1
      into next_number
      from public.campaign_sessions s
     where s.campaign_id = p_campaign_id;

    insert into public.campaign_sessions(
        campaign_id,
        session_number,
        started_by_user_id
    )
    values (p_campaign_id, next_number, current_user_id)
    returning * into new_session;

    captured := private.did_capture_session_snapshots(new_session.id, 'start');

    return query
    select
        new_session.id,
        new_session.campaign_id,
        new_session.session_number,
        new_session.started_at,
        new_session.ended_at,
        captured;
end;
$$;

create or replace function public.did_start_session(
    p_campaign_id uuid
)
returns table (
    id uuid,
    campaign_id uuid,
    session_number integer,
    started_at timestamptz,
    ended_at timestamptz,
    snapshot_count integer
)
language sql
set search_path = ''
as $$
    select * from private.did_start_session_impl(p_campaign_id);
$$;

create or replace function private.did_end_session_impl(
    p_campaign_id uuid
)
returns table (
    id uuid,
    campaign_id uuid,
    session_number integer,
    started_at timestamptz,
    ended_at timestamptz,
    snapshot_count integer
)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
    target_session public.campaign_sessions%rowtype;
    captured integer := 0;
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    if not private.did_is_campaign_dm(p_campaign_id, current_user_id) then
        raise exception 'Only the campaign DM can end a session';
    end if;

    select s.*
      into target_session
      from public.campaign_sessions s
     where s.campaign_id = p_campaign_id
       and s.ended_at is null
     order by s.started_at desc
     limit 1
     for update;

    if target_session.id is null then
        raise exception 'This campaign does not have an active session';
    end if;

    captured := private.did_capture_session_snapshots(target_session.id, 'end');

    update public.campaign_sessions s
       set ended_at = now()
     where s.id = target_session.id
     returning * into target_session;

    return query
    select
        target_session.id,
        target_session.campaign_id,
        target_session.session_number,
        target_session.started_at,
        target_session.ended_at,
        captured;
end;
$$;

create or replace function public.did_end_session(
    p_campaign_id uuid
)
returns table (
    id uuid,
    campaign_id uuid,
    session_number integer,
    started_at timestamptz,
    ended_at timestamptz,
    snapshot_count integer
)
language sql
set search_path = ''
as $$
    select * from private.did_end_session_impl(p_campaign_id);
$$;

revoke all on function private.did_start_session_impl(uuid) from public, anon;
revoke all on function private.did_end_session_impl(uuid) from public, anon;
revoke all on function public.did_start_session(uuid) from public, anon;
revoke all on function public.did_end_session(uuid) from public, anon;

grant execute on function private.did_start_session_impl(uuid) to authenticated;
grant execute on function private.did_end_session_impl(uuid) to authenticated;
grant execute on function public.did_start_session(uuid) to authenticated;
grant execute on function public.did_end_session(uuid) to authenticated;

create or replace function private.did_assign_roll_session()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    target_campaign_id uuid;
    active_session_id uuid;
    share_rolls boolean := true;
begin
    select c.campaign_id, c.share_session_rolls
      into target_campaign_id, share_rolls
      from public.campaign_characters c
     where c.id = new.campaign_character_id;

    if target_campaign_id is null then
        return new;
    end if;

    active_session_id := private.did_active_session_id(target_campaign_id);

    if active_session_id is not null then
        if not coalesce(share_rolls, true) then
            return null;
        end if;
        new.session_id := active_session_id;
    else
        new.session_id := null;
    end if;

    return new;
end;
$$;

drop trigger if exists did_campaign_roll_session on public.campaign_rolls;
create trigger did_campaign_roll_session
before insert on public.campaign_rolls
for each row execute function private.did_assign_roll_session();

alter table public.campaign_sessions enable row level security;
alter table public.session_snapshots enable row level security;

drop policy if exists did_sessions_select on public.campaign_sessions;
drop policy if exists did_snapshots_select on public.session_snapshots;

create policy did_sessions_select
on public.campaign_sessions for select
to authenticated
using (private.did_is_campaign_member(campaign_id, auth.uid()));

create policy did_snapshots_select
on public.session_snapshots for select
to authenticated
using (
    exists (
        select 1
        from public.campaign_sessions s
        where s.id = session_id
          and private.did_is_campaign_dm(s.campaign_id, auth.uid())
    )
);

revoke all on public.campaign_sessions from anon, authenticated;
revoke all on public.session_snapshots from anon, authenticated;

grant select on public.campaign_sessions to authenticated;
grant select on public.session_snapshots to authenticated;

grant update (share_session_rolls)
on public.campaign_characters
to authenticated;

do $$
begin
    if exists (
        select 1 from pg_publication where pubname = 'supabase_realtime'
    ) then
        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'campaign_sessions'
        ) then
            execute 'alter publication supabase_realtime add table public.campaign_sessions';
        end if;
    end if;
end
$$;

commit;
