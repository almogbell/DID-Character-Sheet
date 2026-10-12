-- DID Character Sheet — Phase 7 hotfix 01
-- Fix PostgREST merge-duplicates upsert privileges for party_character_state.
-- Safe to run more than once.

begin;

-- upload_party_state sends campaign_character_id, campaign_id and state with
-- Prefer: resolution=merge-duplicates. PostgREST generates an ON CONFLICT DO
-- UPDATE that may assign campaign_id as well as state, so UPDATE(state) alone
-- is insufficient and PostgreSQL reports "permission denied for table
-- party_character_state" before RLS is evaluated.
--
-- RLS still prevents moving a row to a different campaign because
-- did_party_state_update WITH CHECK requires campaign_id to match the owning
-- campaign_characters row for auth.uid().

grant select on public.party_character_state to authenticated;
grant insert (campaign_character_id, campaign_id, state)
on public.party_character_state to authenticated;
grant update (campaign_id, state)
on public.party_character_state to authenticated;
grant delete on public.party_character_state to authenticated;

commit;
