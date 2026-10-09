-- DID Character Sheet — Campaign Cloud / Phase 2
-- Run this entire file once in the Supabase SQL Editor.
--
-- Security model:
--   * The desktop app uses a publishable/anon project key plus Supabase
--     Anonymous Auth. Anonymous Auth users are authenticated users with a
--     unique auth.uid(), so RLS can isolate campaigns and characters.
--   * DM/owner can read every linked character and roll in their campaign.
--   * A player can read/write only their own linked character and rolls.
--   * The service_role / secret key is NEVER used by the desktop app.

begin;

create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;

-- ============================================================
-- TABLES
-- ============================================================

create table if not exists public.campaigns (
    id uuid primary key default gen_random_uuid(),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    owner_user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    name text not null check (char_length(trim(name)) between 1 and 100),
    invite_code text not null unique,
    active boolean not null default true
);

create table if not exists public.campaign_members (
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    user_id uuid not null references auth.users(id) on delete cascade,
    role text not null check (role in ('dm', 'player')),
    display_name text not null default 'Player' check (char_length(trim(display_name)) between 1 and 80),
    joined_at timestamptz not null default now(),
    primary key (campaign_id, user_id)
);

create table if not exists public.campaign_characters (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    owner_user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
    character_id text not null check (char_length(trim(character_id)) between 1 and 200),
    display_name text not null default 'Unnamed Character' check (char_length(trim(display_name)) between 1 and 120),
    active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (campaign_id, owner_user_id, character_id)
);

create table if not exists public.character_state (
    campaign_character_id uuid primary key references public.campaign_characters(id) on delete cascade,
    state jsonb not null,
    updated_at timestamptz not null default now(),
    check (jsonb_typeof(state) = 'object')
);

create table if not exists public.campaign_rolls (
    event_id uuid primary key,
    campaign_character_id uuid not null references public.campaign_characters(id) on delete cascade,
    rolled_at timestamptz not null,
    created_at timestamptz not null default now(),
    event jsonb not null,
    check (jsonb_typeof(event) = 'object')
);

create index if not exists campaign_members_user_idx
    on public.campaign_members(user_id, campaign_id);
create index if not exists campaign_characters_campaign_idx
    on public.campaign_characters(campaign_id, active, created_at);
create index if not exists campaign_characters_owner_idx
    on public.campaign_characters(owner_user_id, campaign_id);
create index if not exists campaign_rolls_character_time_idx
    on public.campaign_rolls(campaign_character_id, rolled_at desc);

-- ============================================================
-- SMALL PRIVATE HELPERS USED BY RLS
-- ============================================================

create or replace function private.did_is_campaign_member(
    p_campaign_id uuid,
    p_user_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select p_user_id is not null and exists (
        select 1
        from public.campaign_members m
        where m.campaign_id = p_campaign_id
          and m.user_id = p_user_id
    );
$$;

create or replace function private.did_is_campaign_dm(
    p_campaign_id uuid,
    p_user_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select p_user_id is not null and exists (
        select 1
        from public.campaign_members m
        where m.campaign_id = p_campaign_id
          and m.user_id = p_user_id
          and m.role = 'dm'
    );
$$;

create or replace function private.did_owns_campaign_character(
    p_campaign_character_id uuid,
    p_user_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select p_user_id is not null and exists (
        select 1
        from public.campaign_characters c
        where c.id = p_campaign_character_id
          and c.owner_user_id = p_user_id
    );
$$;

create or replace function private.did_can_read_campaign_character(
    p_campaign_character_id uuid,
    p_user_id uuid
)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
    select p_user_id is not null and exists (
        select 1
        from public.campaign_characters c
        where c.id = p_campaign_character_id
          and (
              c.owner_user_id = p_user_id
              or private.did_is_campaign_dm(c.campaign_id, p_user_id)
          )
    );
$$;

revoke all on function private.did_is_campaign_member(uuid, uuid) from public, anon;
revoke all on function private.did_is_campaign_dm(uuid, uuid) from public, anon;
revoke all on function private.did_owns_campaign_character(uuid, uuid) from public, anon;
revoke all on function private.did_can_read_campaign_character(uuid, uuid) from public, anon;
grant execute on function private.did_is_campaign_member(uuid, uuid) to authenticated;
grant execute on function private.did_is_campaign_dm(uuid, uuid) to authenticated;
grant execute on function private.did_owns_campaign_character(uuid, uuid) to authenticated;
grant execute on function private.did_can_read_campaign_character(uuid, uuid) to authenticated;

-- ============================================================
-- INVITE CODE GENERATION
-- ============================================================

create or replace function private.did_new_invite_code()
returns text
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    candidate text;
    attempt integer := 0;
begin
    loop
        attempt := attempt + 1;
        candidate := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 8));
        if not exists (
            select 1 from public.campaigns c where c.invite_code = candidate
        ) then
            return candidate;
        end if;
        if attempt >= 20 then
            raise exception 'Could not allocate a unique campaign invite code';
        end if;
    end loop;
end;
$$;

revoke all on function private.did_new_invite_code() from public, anon, authenticated;
alter table public.campaigns alter column invite_code set default private.did_new_invite_code();

-- ============================================================
-- TIMESTAMPS + AUTOMATIC DM MEMBERSHIP
-- ============================================================

create or replace function private.did_touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
    new.updated_at := now();
    return new;
end;
$$;

create or replace function private.did_add_campaign_owner_member()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
    insert into public.campaign_members(campaign_id, user_id, role, display_name)
    values (new.id, new.owner_user_id, 'dm', 'DM')
    on conflict (campaign_id, user_id) do nothing;
    return new;
end;
$$;

drop trigger if exists did_campaigns_touch_updated_at on public.campaigns;
create trigger did_campaigns_touch_updated_at
before update on public.campaigns
for each row execute function private.did_touch_updated_at();

drop trigger if exists did_campaign_characters_touch_updated_at on public.campaign_characters;
create trigger did_campaign_characters_touch_updated_at
before update on public.campaign_characters
for each row execute function private.did_touch_updated_at();

drop trigger if exists did_campaign_owner_membership on public.campaigns;
create trigger did_campaign_owner_membership
after insert on public.campaigns
for each row execute function private.did_add_campaign_owner_member();

-- ============================================================
-- JOIN BY INVITE CODE
-- Public RPC is security-invoker; the privileged work is in private schema.
-- ============================================================

create or replace function private.did_join_campaign_impl(
    p_invite_code text,
    p_display_name text
)
returns table (
    id uuid,
    name text,
    invite_code text,
    owner_user_id uuid,
    role text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
    target_campaign public.campaigns%rowtype;
    final_role text;
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    select c.*
      into target_campaign
      from public.campaigns c
     where c.invite_code = upper(replace(trim(coalesce(p_invite_code, '')), ' ', ''))
       and c.active = true
     limit 1;

    if target_campaign.id is null then
        return;
    end if;

    insert into public.campaign_members(campaign_id, user_id, role, display_name)
    values (
        target_campaign.id,
        current_user_id,
        'player',
        left(coalesce(nullif(trim(p_display_name), ''), 'Player'), 80)
    )
    on conflict (campaign_id, user_id)
    do update set display_name = excluded.display_name;

    select m.role
      into final_role
      from public.campaign_members m
     where m.campaign_id = target_campaign.id
       and m.user_id = current_user_id;

    return query
    select
        target_campaign.id,
        target_campaign.name,
        target_campaign.invite_code,
        target_campaign.owner_user_id,
        final_role;
end;
$$;

create or replace function public.did_join_campaign(
    p_invite_code text,
    p_display_name text default 'Player'
)
returns table (
    id uuid,
    name text,
    invite_code text,
    owner_user_id uuid,
    role text
)
language sql
set search_path = ''
as $$
    select * from private.did_join_campaign_impl(p_invite_code, p_display_name);
$$;

revoke all on function private.did_join_campaign_impl(text, text) from public, anon;
grant execute on function private.did_join_campaign_impl(text, text) to authenticated;
revoke all on function public.did_join_campaign(text, text) from public, anon;
grant execute on function public.did_join_campaign(text, text) to authenticated;

-- ============================================================
-- RLS
-- ============================================================

alter table public.campaigns enable row level security;
alter table public.campaign_members enable row level security;
alter table public.campaign_characters enable row level security;
alter table public.character_state enable row level security;
alter table public.campaign_rolls enable row level security;

-- Remove previous Phase 2 policy names if this file is re-run.
drop policy if exists did_campaigns_select on public.campaigns;
drop policy if exists did_campaigns_insert on public.campaigns;
drop policy if exists did_campaigns_update on public.campaigns;
drop policy if exists did_campaigns_delete on public.campaigns;

drop policy if exists did_members_select on public.campaign_members;
drop policy if exists did_members_update on public.campaign_members;
drop policy if exists did_members_delete on public.campaign_members;

drop policy if exists did_characters_select on public.campaign_characters;
drop policy if exists did_characters_insert on public.campaign_characters;
drop policy if exists did_characters_update on public.campaign_characters;
drop policy if exists did_characters_delete on public.campaign_characters;

drop policy if exists did_state_select on public.character_state;
drop policy if exists did_state_insert on public.character_state;
drop policy if exists did_state_update on public.character_state;
drop policy if exists did_state_delete on public.character_state;

drop policy if exists did_rolls_select on public.campaign_rolls;
drop policy if exists did_rolls_insert on public.campaign_rolls;

create policy did_campaigns_select
on public.campaigns for select
to authenticated
using (private.did_is_campaign_member(id, auth.uid()));

create policy did_campaigns_insert
on public.campaigns for insert
to authenticated
with check (auth.uid() is not null and owner_user_id = auth.uid());

create policy did_campaigns_update
on public.campaigns for update
to authenticated
using (owner_user_id = auth.uid())
with check (owner_user_id = auth.uid());

create policy did_campaigns_delete
on public.campaigns for delete
to authenticated
using (owner_user_id = auth.uid());

create policy did_members_select
on public.campaign_members for select
to authenticated
using (
    user_id = auth.uid()
    or private.did_is_campaign_dm(campaign_id, auth.uid())
);

create policy did_members_update
on public.campaign_members for update
to authenticated
using (user_id = auth.uid())
with check (user_id = auth.uid());

create policy did_members_delete
on public.campaign_members for delete
to authenticated
using (
    role <> 'dm'
    and (
        user_id = auth.uid()
        or private.did_is_campaign_dm(campaign_id, auth.uid())
    )
);

create policy did_characters_select
on public.campaign_characters for select
to authenticated
using (
    owner_user_id = auth.uid()
    or private.did_is_campaign_dm(campaign_id, auth.uid())
);

create policy did_characters_insert
on public.campaign_characters for insert
to authenticated
with check (
    owner_user_id = auth.uid()
    and private.did_is_campaign_member(campaign_id, auth.uid())
);

create policy did_characters_update
on public.campaign_characters for update
to authenticated
using (owner_user_id = auth.uid())
with check (
    owner_user_id = auth.uid()
    and private.did_is_campaign_member(campaign_id, auth.uid())
);

create policy did_characters_delete
on public.campaign_characters for delete
to authenticated
using (owner_user_id = auth.uid());

create policy did_state_select
on public.character_state for select
to authenticated
using (
    private.did_can_read_campaign_character(campaign_character_id, auth.uid())
);

create policy did_state_insert
on public.character_state for insert
to authenticated
with check (
    private.did_owns_campaign_character(campaign_character_id, auth.uid())
);

create policy did_state_update
on public.character_state for update
to authenticated
using (
    private.did_owns_campaign_character(campaign_character_id, auth.uid())
)
with check (
    private.did_owns_campaign_character(campaign_character_id, auth.uid())
);

create policy did_state_delete
on public.character_state for delete
to authenticated
using (
    private.did_owns_campaign_character(campaign_character_id, auth.uid())
);

create policy did_rolls_select
on public.campaign_rolls for select
to authenticated
using (
    private.did_can_read_campaign_character(campaign_character_id, auth.uid())
);

create policy did_rolls_insert
on public.campaign_rolls for insert
to authenticated
with check (
    private.did_owns_campaign_character(campaign_character_id, auth.uid())
);

-- ============================================================
-- TABLE PRIVILEGES
-- RLS is not a substitute for grants: expose only the operations/columns used.
-- ============================================================

revoke all on public.campaigns from anon, authenticated;
revoke all on public.campaign_members from anon, authenticated;
revoke all on public.campaign_characters from anon, authenticated;
revoke all on public.character_state from anon, authenticated;
revoke all on public.campaign_rolls from anon, authenticated;

grant select on public.campaigns to authenticated;
grant insert (name) on public.campaigns to authenticated;
grant update (name, active) on public.campaigns to authenticated;
grant delete on public.campaigns to authenticated;

grant select on public.campaign_members to authenticated;
grant update (display_name) on public.campaign_members to authenticated;
grant delete on public.campaign_members to authenticated;

grant select on public.campaign_characters to authenticated;
grant insert (campaign_id, character_id, display_name, active) on public.campaign_characters to authenticated;
grant update (display_name, active) on public.campaign_characters to authenticated;
grant delete on public.campaign_characters to authenticated;

grant select on public.character_state to authenticated;
grant insert (campaign_character_id, state) on public.character_state to authenticated;
grant update (state) on public.character_state to authenticated;
grant delete on public.character_state to authenticated;

grant select on public.campaign_rolls to authenticated;
grant insert (event_id, campaign_character_id, rolled_at, event) on public.campaign_rolls to authenticated;

commit;
