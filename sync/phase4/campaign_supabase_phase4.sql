-- DID Character Sheet — Phase 4
-- DM browser dashboard, secure browser claim code, presence heartbeat and Realtime.
-- Run this whole file in the SAME Supabase project after Phase 3.
-- Safe to run more than once.

begin;

alter table public.campaign_characters
add column if not exists last_seen_at timestamptz;

create table if not exists private.did_dashboard_invites (
    campaign_id uuid primary key references public.campaigns(id) on delete cascade,
    code text not null unique,
    expires_at timestamptz not null,
    created_at timestamptz not null default now()
);

revoke all on private.did_dashboard_invites from public, anon, authenticated;

create or replace function private.did_new_dashboard_code()
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
            from private.did_dashboard_invites i
            where i.code = candidate
        ) then
            return candidate;
        end if;
        if attempt >= 20 then
            raise exception 'Could not allocate a dashboard access code';
        end if;
    end loop;
end;
$$;

create or replace function private.did_create_dashboard_code_impl(
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

    if not exists (
        select 1
        from public.campaigns c
        where c.id = p_campaign_id
          and c.owner_user_id = current_user_id
          and c.active = true
    ) then
        raise exception 'Only the campaign owner can open the DM dashboard';
    end if;

    generated_code := private.did_new_dashboard_code();

    insert into private.did_dashboard_invites(
        campaign_id,
        code,
        expires_at,
        created_at
    )
    values (
        p_campaign_id,
        generated_code,
        expiry,
        now()
    )
    on conflict (campaign_id)
    do update set
        code = excluded.code,
        expires_at = excluded.expires_at,
        created_at = now();

    return query
    select generated_code, expiry;
end;
$$;

create or replace function public.did_create_dashboard_code(
    p_campaign_id uuid
)
returns table (
    dashboard_code text,
    expires_at timestamptz
)
language sql
set search_path = ''
as $$
    select *
    from private.did_create_dashboard_code_impl(p_campaign_id);
$$;

create or replace function private.did_claim_dashboard_impl(
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
      from private.did_dashboard_invites i
      join public.campaigns c on c.id = i.campaign_id
     where i.code = normalized_code
       and i.expires_at > now()
       and c.active = true
     limit 1
     for update of i;

    if target_campaign_id is null then
        return;
    end if;

    delete from private.did_dashboard_invites
     where campaign_id = target_campaign_id;

    insert into public.campaign_members(
        campaign_id,
        user_id,
        role,
        display_name
    )
    values (
        target_campaign_id,
        current_user_id,
        'dm',
        'DM Dashboard'
    )
    on conflict (campaign_id, user_id)
    do update set
        role = 'dm',
        display_name = 'DM Dashboard';

    return query
    select
        target_campaign_id,
        target_campaign_name,
        'dm'::text;
end;
$$;

create or replace function public.did_claim_dashboard(
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
    select *
    from private.did_claim_dashboard_impl(p_dashboard_code);
$$;

revoke all on function private.did_new_dashboard_code() from public, anon, authenticated;
revoke all on function private.did_create_dashboard_code_impl(uuid) from public, anon;
revoke all on function private.did_claim_dashboard_impl(text) from public, anon;
revoke all on function public.did_create_dashboard_code(uuid) from public, anon;
revoke all on function public.did_claim_dashboard(text) from public, anon;

grant execute on function private.did_create_dashboard_code_impl(uuid) to authenticated;
grant execute on function private.did_claim_dashboard_impl(text) to authenticated;
grant execute on function public.did_create_dashboard_code(uuid) to authenticated;
grant execute on function public.did_claim_dashboard(text) to authenticated;

-- Player desktop heartbeat. Existing row-update RLS still requires ownership.
grant update (last_seen_at)
on public.campaign_characters
to authenticated;

-- Realtime publication for the dashboard data sources.
do $$
begin
    if exists (
        select 1
        from pg_publication
        where pubname = 'supabase_realtime'
    ) then
        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'campaign_characters'
        ) then
            execute 'alter publication supabase_realtime add table public.campaign_characters';
        end if;

        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'character_state'
        ) then
            execute 'alter publication supabase_realtime add table public.character_state';
        end if;

        if not exists (
            select 1 from pg_publication_tables
            where pubname = 'supabase_realtime'
              and schemaname = 'public'
              and tablename = 'campaign_rolls'
        ) then
            execute 'alter publication supabase_realtime add table public.campaign_rolls';
        end if;
    end if;
end
$$;

commit;
