-- DID Character Sheet — Phase 7 live Party Dashboard
-- Adds party-visible session rolls while preserving player roll-sharing choice.
-- Run after campaign_supabase_phase7.sql. Safe to run more than once.

begin;

create table if not exists public.party_session_rolls (
    event_id uuid primary key references public.campaign_rolls(event_id) on delete cascade,
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    session_id uuid not null references public.campaign_sessions(id) on delete cascade,
    campaign_character_id uuid not null references public.campaign_characters(id) on delete cascade,
    rolled_at timestamptz not null,
    event jsonb not null,
    created_at timestamptz not null default now(),
    check (jsonb_typeof(event) = 'object')
);

create index if not exists did_party_session_rolls_campaign_time_idx
on public.party_session_rolls(campaign_id, rolled_at desc);

create index if not exists did_party_session_rolls_session_time_idx
on public.party_session_rolls(session_id, rolled_at desc);

alter table public.party_session_rolls enable row level security;

drop policy if exists did_party_session_rolls_select on public.party_session_rolls;
create policy did_party_session_rolls_select
on public.party_session_rolls for select
to authenticated
using (
    private.did_is_campaign_member(campaign_id, auth.uid())
);

revoke all on public.party_session_rolls from public, anon, authenticated;
grant select on public.party_session_rolls to authenticated;

-- campaign_rolls already has the Phase 5 BEFORE INSERT trigger that assigns
-- session_id and suppresses the insert entirely when the player disabled
-- "Share my dice rolls during active sessions". Therefore this AFTER INSERT
-- mirror receives only rolls the player actually chose to share.
create or replace function private.did_mirror_party_session_roll()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
    target_campaign_id uuid;
begin
    if new.session_id is null then
        return new;
    end if;

    select cc.campaign_id
      into target_campaign_id
      from public.campaign_characters cc
     where cc.id = new.campaign_character_id
       and cc.active = true
     limit 1;

    if target_campaign_id is null then
        return new;
    end if;

    insert into public.party_session_rolls(
        event_id,
        campaign_id,
        session_id,
        campaign_character_id,
        rolled_at,
        event
    )
    values (
        new.event_id,
        target_campaign_id,
        new.session_id,
        new.campaign_character_id,
        new.rolled_at,
        new.event
    )
    on conflict (event_id) do nothing;

    return new;
end;
$$;

revoke all on function private.did_mirror_party_session_roll() from public, anon, authenticated;

drop trigger if exists did_party_session_roll_mirror on public.campaign_rolls;
create trigger did_party_session_roll_mirror
after insert on public.campaign_rolls
for each row execute function private.did_mirror_party_session_roll();

-- Realtime is supplemental. The dashboard still refreshes manually if this
-- publication is unavailable.
do $$
begin
    if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'party_session_rolls'
        ) then
            execute 'alter publication supabase_realtime add table public.party_session_rolls';
        end if;
    end if;
end
$$;

commit;
