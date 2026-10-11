-- DID Character Sheet — Phase 7
-- Role-separated campaign UX, Party Dashboard sharing, and DM character removal.
-- Run after the Phase 5 Supabase migration. Safe to run more than once.

begin;

-- ============================================================
-- Party-visible character state
-- ============================================================

create table if not exists public.party_character_state (
    campaign_character_id uuid primary key references public.campaign_characters(id) on delete cascade,
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    state jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);

create index if not exists did_party_character_state_campaign_idx
on public.party_character_state(campaign_id, updated_at desc);

alter table public.party_character_state enable row level security;

drop policy if exists did_party_state_select on public.party_character_state;
drop policy if exists did_party_state_insert on public.party_character_state;
drop policy if exists did_party_state_update on public.party_character_state;
drop policy if exists did_party_state_delete on public.party_character_state;

create policy did_party_state_select
on public.party_character_state for select
to authenticated
using (
    private.did_is_campaign_member(campaign_id, auth.uid())
);

create policy did_party_state_insert
on public.party_character_state for insert
to authenticated
with check (
    exists (
        select 1
        from public.campaign_characters cc
        where cc.id = campaign_character_id
          and cc.campaign_id = campaign_id
          and cc.owner_user_id = auth.uid()
          and cc.active = true
    )
);

create policy did_party_state_update
on public.party_character_state for update
to authenticated
using (
    exists (
        select 1
        from public.campaign_characters cc
        where cc.id = campaign_character_id
          and cc.owner_user_id = auth.uid()
          and cc.active = true
    )
)
with check (
    exists (
        select 1
        from public.campaign_characters cc
        where cc.id = campaign_character_id
          and cc.campaign_id = campaign_id
          and cc.owner_user_id = auth.uid()
          and cc.active = true
    )
);

create policy did_party_state_delete
on public.party_character_state for delete
to authenticated
using (
    exists (
        select 1
        from public.campaign_characters cc
        where cc.id = campaign_character_id
          and cc.owner_user_id = auth.uid()
    )
);

revoke all on public.party_character_state from anon, authenticated;
grant select on public.party_character_state to authenticated;
grant insert (campaign_character_id, campaign_id, state) on public.party_character_state to authenticated;
grant update (state) on public.party_character_state to authenticated;
grant delete on public.party_character_state to authenticated;

-- Keep updated_at reliable on upsert.
drop trigger if exists did_party_state_touch_updated_at on public.party_character_state;
create trigger did_party_state_touch_updated_at
before update on public.party_character_state
for each row
execute function private.did_touch_updated_at();

-- ============================================================
-- DM removes a character from the live campaign roster.
-- This is intentionally a soft removal so historical session data survives.
-- ============================================================

create or replace function private.did_remove_campaign_character_impl(
    p_campaign_character_id uuid
)
returns boolean
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
    target_campaign_id uuid;
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    select cc.campaign_id
      into target_campaign_id
      from public.campaign_characters cc
     where cc.id = p_campaign_character_id
     limit 1;

    if target_campaign_id is null then
        return false;
    end if;

    if not private.did_is_campaign_dm(target_campaign_id, current_user_id) then
        raise exception 'Only the campaign DM can remove a campaign character';
    end if;

    update public.campaign_characters
       set active = false,
           updated_at = now()
     where id = p_campaign_character_id;

    delete from public.party_character_state
     where campaign_character_id = p_campaign_character_id;

    return true;
end;
$$;

create or replace function public.did_remove_campaign_character(
    p_campaign_character_id uuid
)
returns boolean
language sql
set search_path = ''
as $$
    select private.did_remove_campaign_character_impl(p_campaign_character_id);
$$;

revoke all on function private.did_remove_campaign_character_impl(uuid) from public, anon;
revoke all on function public.did_remove_campaign_character(uuid) from public, anon;
grant execute on function private.did_remove_campaign_character_impl(uuid) to authenticated;
grant execute on function public.did_remove_campaign_character(uuid) to authenticated;

-- ============================================================
-- One-time Party Dashboard pairing.
-- Any campaign member can open the shared dashboard.  The browser receives
-- only a normal player membership, never DM privileges.
-- ============================================================

create table if not exists private.did_party_dashboard_invites (
    id uuid primary key default gen_random_uuid(),
    campaign_id uuid not null references public.campaigns(id) on delete cascade,
    created_by_user_id uuid not null references auth.users(id) on delete cascade,
    code text not null unique,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

revoke all on private.did_party_dashboard_invites from public, anon, authenticated;

create or replace function private.did_new_party_dashboard_code()
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
        candidate := upper(substr(replace(gen_random_uuid()::text, '-', ''), 1, 10));
        if not exists (
            select 1
            from private.did_party_dashboard_invites i
            where i.code = candidate
        ) then
            return candidate;
        end if;
        if attempt >= 20 then
            raise exception 'Could not allocate a Party Dashboard access code';
        end if;
    end loop;
end;
$$;

create or replace function private.did_create_party_dashboard_code_impl(
    p_campaign_id uuid
)
returns table (
    dashboard_code text,
    expires_at timestamptz
)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
    generated_code text;
    expiry timestamptz := now() + interval '10 minutes';
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    if not private.did_is_campaign_member(p_campaign_id, current_user_id) then
        raise exception 'You are not a member of this campaign';
    end if;

    delete from private.did_party_dashboard_invites
     where created_by_user_id = current_user_id
       and campaign_id = p_campaign_id;

    generated_code := private.did_new_party_dashboard_code();

    insert into private.did_party_dashboard_invites(
        campaign_id,
        created_by_user_id,
        code,
        expires_at
    )
    values (
        p_campaign_id,
        current_user_id,
        generated_code,
        expiry
    );

    return query select generated_code, expiry;
end;
$$;

create or replace function public.did_create_party_dashboard_code(
    p_campaign_id uuid
)
returns table (
    dashboard_code text,
    expires_at timestamptz
)
language sql
set search_path = ''
as $$
    select * from private.did_create_party_dashboard_code_impl(p_campaign_id);
$$;

create or replace function private.did_claim_party_dashboard_impl(
    p_dashboard_code text
)
returns table (
    id uuid,
    name text,
    role text
)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
    normalized_code text := upper(replace(trim(coalesce(p_dashboard_code, '')), ' ', ''));
    target_campaign_id uuid;
    target_campaign_name text;
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    if normalized_code = '' then
        return;
    end if;

    select i.campaign_id, c.name
      into target_campaign_id, target_campaign_name
      from private.did_party_dashboard_invites i
      join public.campaigns c on c.id = i.campaign_id
     where i.code = normalized_code
       and i.expires_at > now()
       and c.active = true
     limit 1
     for update of i;

    if target_campaign_id is null then
        return;
    end if;

    delete from private.did_party_dashboard_invites
     where code = normalized_code;

    insert into public.campaign_members(
        campaign_id,
        user_id,
        role,
        display_name
    )
    values (
        target_campaign_id,
        current_user_id,
        'player',
        'Party Dashboard'
    )
    on conflict (campaign_id, user_id)
    do update set
        role = case
            when public.campaign_members.role = 'dm' then 'dm'
            else 'player'
        end,
        display_name = case
            when public.campaign_members.role = 'dm' then public.campaign_members.display_name
            else 'Party Dashboard'
        end;

    return query
    select target_campaign_id, target_campaign_name, 'player'::text;
end;
$$;

create or replace function public.did_claim_party_dashboard(
    p_dashboard_code text
)
returns table (
    id uuid,
    name text,
    role text
)
language sql
set search_path = ''
as $$
    select * from private.did_claim_party_dashboard_impl(p_dashboard_code);
$$;

revoke all on function private.did_new_party_dashboard_code() from public, anon, authenticated;
revoke all on function private.did_create_party_dashboard_code_impl(uuid) from public, anon;
revoke all on function private.did_claim_party_dashboard_impl(text) from public, anon;
revoke all on function public.did_create_party_dashboard_code(uuid) from public, anon;
revoke all on function public.did_claim_party_dashboard(text) from public, anon;

grant execute on function private.did_create_party_dashboard_code_impl(uuid) to authenticated;
grant execute on function private.did_claim_party_dashboard_impl(text) to authenticated;
grant execute on function public.did_create_party_dashboard_code(uuid) to authenticated;
grant execute on function public.did_claim_party_dashboard(text) to authenticated;

-- Realtime for the shared Party Dashboard.
do $$
begin
    if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'party_character_state'
        ) then
            execute 'alter publication supabase_realtime add table public.party_character_state';
        end if;
    end if;
end
$$;

commit;
