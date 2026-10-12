-- DID Character Sheet — Live-session-only dashboard update
-- Run after Phase 8. Safe to run more than once.
--
-- New behavior:
--   * no new session snapshots are captured
--   * rolls are stored only while a session is active
--   * rolls from a completed session are removed when the session ends
--   * session rows remain so numbering still works
--
-- Existing old snapshot rows are left untouched; the dashboard no longer reads them.

begin;

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
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    if not private.did_is_campaign_dm(p_campaign_id, current_user_id) then
        raise exception 'Only the campaign DM can start a session';
    end if;

    if exists (
        select 1
        from public.campaign_sessions s
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

    return query
    select
        new_session.id,
        new_session.campaign_id,
        new_session.session_number,
        new_session.started_at,
        new_session.ended_at,
        0::integer;
end;
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

    update public.campaign_sessions s
       set ended_at = now()
     where s.id = target_session.id
     returning * into target_session;

    delete from public.campaign_rolls r
     where r.session_id = target_session.id;

    return query
    select
        target_session.id,
        target_session.campaign_id,
        target_session.session_number,
        target_session.started_at,
        target_session.ended_at,
        0::integer;
end;
$$;

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
        return null;
    end if;

    active_session_id := private.did_active_session_id(target_campaign_id);

    if active_session_id is null then
        return null;
    end if;

    if not coalesce(share_rolls, true) then
        return null;
    end if;

    new.session_id := active_session_id;
    return new;
end;
$$;

commit;
