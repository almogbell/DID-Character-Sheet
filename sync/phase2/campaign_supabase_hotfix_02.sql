-- DID Character Sheet — Campaign Cloud / Phase 2
-- Hotfix 02: allow PostgREST UPSERT to update the conflict-key columns it sends.
--
-- Why this is needed:
-- campaign_cloud.py uses Prefer: resolution=merge-duplicates for idempotent
-- character linking and character-state updates. PostgreSQL requires UPDATE
-- privilege on every column included in the UPSERT's DO UPDATE assignment,
-- including the conflict-key columns that PostgREST includes from the request.
-- RLS still restricts updates to rows owned by auth.uid(), and owner_user_id
-- remains non-updatable.

begin;

-- campaign_characters UPSERT sends campaign_id, character_id, display_name,
-- and active. Keep owner_user_id immutable.
grant update (campaign_id, character_id, display_name, active)
on public.campaign_characters
to authenticated;

-- character_state UPSERT sends both the primary/conflict key and state.
grant update (campaign_character_id, state)
on public.character_state
to authenticated;

commit;
