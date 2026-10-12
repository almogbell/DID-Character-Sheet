-- DID Character Sheet — Phase 7 hotfix 03
-- Fixes PL/pgSQL ambiguity in did_upsert_party_character_state.
-- Safe to run after hotfix 02 and safe to run more than once.

begin;

create or replace function public.did_upsert_party_character_state(
    p_campaign_id uuid,
    p_campaign_character_id uuid,
    p_state jsonb
)
returns table (
    campaign_character_id uuid,
    campaign_id uuid,
    updated_at timestamptz
)
language plpgsql
volatile
security definer
set search_path = ''
as $$
declare
    current_user_id uuid := auth.uid();
begin
    if current_user_id is null then
        raise exception 'Authentication required';
    end if;

    if p_state is null or jsonb_typeof(p_state) <> 'object' then
        raise exception 'Party character state must be a JSON object';
    end if;

    if not exists (
        select 1
        from public.campaign_characters cc
        where cc.id = p_campaign_character_id
          and cc.campaign_id = p_campaign_id
          and cc.owner_user_id = current_user_id
          and cc.active = true
    ) then
        raise exception 'You do not own this active campaign character';
    end if;

    insert into public.party_character_state(
        campaign_character_id,
        campaign_id,
        state
    )
    values (
        p_campaign_character_id,
        p_campaign_id,
        p_state
    )
    on conflict on constraint party_character_state_pkey
    do update set
        campaign_id = excluded.campaign_id,
        state = excluded.state,
        updated_at = now();

    return query
    select pcs.campaign_character_id, pcs.campaign_id, pcs.updated_at
    from public.party_character_state as pcs
    where pcs.campaign_character_id = p_campaign_character_id;
end;
$$;

revoke all on function public.did_upsert_party_character_state(uuid, uuid, jsonb)
from public, anon;
grant execute on function public.did_upsert_party_character_state(uuid, uuid, jsonb)
to authenticated;

commit;
