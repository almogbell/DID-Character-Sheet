-- DID Character Sheet — Phase 8
-- DM campaign layer: private notes, NPCs, relationships, hooks/secrets/clues,
-- player-visible campaign entries, and character effects.
-- Run after Phase 7. Safe to run more than once.

begin;

create table if not exists public.campaign_dm_notes (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    created_by_user_id uuid default auth.uid() references auth.users(id) on delete set null,
    title text not null check (char_length(trim(title)) between 1 and 160),
    body text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.campaign_npcs (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    created_by_user_id uuid default auth.uid() references auth.users(id) on delete set null,
    name text not null check (char_length(trim(name)) between 1 and 160),
    status text not null default '',
    description text not null default '',
    gm_notes text not null default '',
    portrait_url text not null default '',
    visible_to_players boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.campaign_npc_relationships (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    npc_id uuid not null references public.campaign_npcs(id) on delete cascade,
    target_kind text not null check (target_kind in ('npc','character')),
    target_npc_id uuid references public.campaign_npcs(id) on delete cascade,
    target_campaign_character_id uuid references public.campaign_characters(id) on delete cascade,
    relationship text not null check (char_length(trim(relationship)) between 1 and 200),
    notes text not null default '',
    visible_to_players boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
        (target_kind = 'npc' and target_npc_id is not null and target_campaign_character_id is null)
        or
        (target_kind = 'character' and target_campaign_character_id is not null and target_npc_id is null)
    )
);

create table if not exists public.campaign_entries (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    created_by_user_id uuid default auth.uid() references auth.users(id) on delete set null,
    entry_type text not null check (entry_type in ('hook','secret','clue','quest','objective','message')),
    title text not null check (char_length(trim(title)) between 1 and 180),
    body text not null default '',
    status text not null default 'active',
    visible_to_players boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.campaign_character_effects (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    campaign_character_id uuid not null references public.campaign_characters(id) on delete cascade,
    created_by_user_id uuid default auth.uid() references auth.users(id) on delete set null,
    name text not null check (char_length(trim(name)) between 1 and 160),
    description text not null default '',
    status text not null default 'active',
    visible_to_player boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists did_campaign_dm_notes_campaign_idx on public.campaign_dm_notes(campaign_id, updated_at desc);
create index if not exists did_campaign_npcs_campaign_idx on public.campaign_npcs(campaign_id, name);
create index if not exists did_campaign_npc_relationships_campaign_idx on public.campaign_npc_relationships(campaign_id, npc_id);
create index if not exists did_campaign_entries_campaign_idx on public.campaign_entries(campaign_id, entry_type, updated_at desc);
create index if not exists did_campaign_character_effects_campaign_idx on public.campaign_character_effects(campaign_id, campaign_character_id, status);

create or replace function private.did_phase8_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

revoke all on function private.did_phase8_touch_updated_at() from public, anon;
grant execute on function private.did_phase8_touch_updated_at() to authenticated;

do $$
declare t text;
begin
    foreach t in array array['campaign_dm_notes','campaign_npcs','campaign_npc_relationships','campaign_entries','campaign_character_effects']
    loop
        execute format('drop trigger if exists did_%I_touch on public.%I', t, t);
        execute format('create trigger did_%I_touch before update on public.%I for each row execute function private.did_phase8_touch_updated_at()', t, t);
    end loop;
end
$$;

alter table public.campaign_dm_notes enable row level security;
alter table public.campaign_npcs enable row level security;
alter table public.campaign_npc_relationships enable row level security;
alter table public.campaign_entries enable row level security;
alter table public.campaign_character_effects enable row level security;

-- DM notes are always DM-only.
drop policy if exists did_phase8_dm_notes_select on public.campaign_dm_notes;
drop policy if exists did_phase8_dm_notes_write on public.campaign_dm_notes;
create policy did_phase8_dm_notes_select on public.campaign_dm_notes for select to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()));
create policy did_phase8_dm_notes_write on public.campaign_dm_notes for all to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()))
with check (private.did_is_campaign_dm(campaign_id, auth.uid()));

-- NPCs are DM-private unless explicitly revealed.
drop policy if exists did_phase8_npcs_select on public.campaign_npcs;
drop policy if exists did_phase8_npcs_write on public.campaign_npcs;
create policy did_phase8_npcs_select on public.campaign_npcs for select to authenticated
using (
    private.did_is_campaign_dm(campaign_id, auth.uid())
    or (visible_to_players and private.did_is_campaign_member(campaign_id, auth.uid()))
);
create policy did_phase8_npcs_write on public.campaign_npcs for all to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()))
with check (private.did_is_campaign_dm(campaign_id, auth.uid()));

-- Relationships remain DM-only in Phase 8. Visibility is stored for later player UI.
drop policy if exists did_phase8_relationships_select on public.campaign_npc_relationships;
drop policy if exists did_phase8_relationships_write on public.campaign_npc_relationships;
create policy did_phase8_relationships_select on public.campaign_npc_relationships for select to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()));
create policy did_phase8_relationships_write on public.campaign_npc_relationships for all to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()))
with check (private.did_is_campaign_dm(campaign_id, auth.uid()));

-- Hooks/secrets can become player-visible campaign information when explicitly revealed.
drop policy if exists did_phase8_entries_select on public.campaign_entries;
drop policy if exists did_phase8_entries_write on public.campaign_entries;
create policy did_phase8_entries_select on public.campaign_entries for select to authenticated
using (
    private.did_is_campaign_dm(campaign_id, auth.uid())
    or (visible_to_players and private.did_is_campaign_member(campaign_id, auth.uid()))
);
create policy did_phase8_entries_write on public.campaign_entries for all to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()))
with check (private.did_is_campaign_dm(campaign_id, auth.uid()));

-- Effects are visible to the DM, or to the owner of the affected character when revealed.
drop policy if exists did_phase8_effects_select on public.campaign_character_effects;
drop policy if exists did_phase8_effects_write on public.campaign_character_effects;
create policy did_phase8_effects_select on public.campaign_character_effects for select to authenticated
using (
    private.did_is_campaign_dm(campaign_id, auth.uid())
    or (
        visible_to_player
        and private.did_owns_campaign_character(campaign_character_id, auth.uid())
    )
);
create policy did_phase8_effects_write on public.campaign_character_effects for all to authenticated
using (private.did_is_campaign_dm(campaign_id, auth.uid()))
with check (
    private.did_is_campaign_dm(campaign_id, auth.uid())
    and exists (
        select 1 from public.campaign_characters cc
        where cc.id = campaign_character_id
          and cc.campaign_id = campaign_id
    )
);

revoke all on public.campaign_dm_notes from public, anon, authenticated;
revoke all on public.campaign_npcs from public, anon, authenticated;
revoke all on public.campaign_npc_relationships from public, anon, authenticated;
revoke all on public.campaign_entries from public, anon, authenticated;
revoke all on public.campaign_character_effects from public, anon, authenticated;

grant select, insert, update, delete on public.campaign_dm_notes to authenticated;
grant select, insert, update, delete on public.campaign_npcs to authenticated;
grant select, insert, update, delete on public.campaign_npc_relationships to authenticated;
grant select, insert, update, delete on public.campaign_entries to authenticated;
grant select, insert, update, delete on public.campaign_character_effects to authenticated;

-- Realtime is optional; manual Refresh still works.
do $$
declare t text;
begin
    if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
        foreach t in array array['campaign_dm_notes','campaign_npcs','campaign_npc_relationships','campaign_entries','campaign_character_effects']
        loop
            if not exists (
                select 1 from pg_publication_tables
                where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = t
            ) then
                execute format('alter publication supabase_realtime add table public.%I', t);
            end if;
        end loop;
    end if;
end
$$;

commit;
