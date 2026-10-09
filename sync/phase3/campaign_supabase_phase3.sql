-- DID Character Sheet — Phase 3
-- Campaigns now contain their CharacterTemplate / Creation Rules.
--
-- Run this whole file in the SAME Supabase project after Phase 2.
-- It is safe to run more than once.

begin;

alter table public.campaigns
add column if not exists character_template jsonb;

update public.campaigns
set character_template = jsonb_build_object(
    'name', coalesce(nullif(trim(name), ''), 'Campaign') || ' Rules',
    'description', '',
    'player_instructions', '',
    'rules', jsonb_build_object(
        'level', 1,
        'extra_ip', 0,
        'species_mode', 'normal',
        'starting_hearts', null,
        'starting_at', null,
        'allow_custom_improvements', true,
        'allowed_ability_array_ids', jsonb_build_array(),
        'free_heightened_ability_slots', 2,
        'restrict_ability_dice_to_allowed_arrays', false,
        'improvement_mode', 'all',
        'improvement_ids', jsonb_build_array(),
        'improvement_overrides', jsonb_build_object(),
        'template_custom_improvements', jsonb_build_array()
    )
)
where character_template is null;

alter table public.campaigns
alter column character_template set default
'{
  "name": "Campaign Rules",
  "description": "",
  "player_instructions": "",
  "rules": {
    "level": 1,
    "extra_ip": 0,
    "species_mode": "normal",
    "starting_hearts": null,
    "starting_at": null,
    "allow_custom_improvements": true,
    "allowed_ability_array_ids": [],
    "free_heightened_ability_slots": 2,
    "restrict_ability_dice_to_allowed_arrays": false,
    "improvement_mode": "all",
    "improvement_ids": [],
    "improvement_overrides": {},
    "template_custom_improvements": []
  }
}'::jsonb;

alter table public.campaigns
alter column character_template set not null;

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'did_campaign_character_template_object'
          and conrelid = 'public.campaigns'::regclass
    ) then
        alter table public.campaigns
        add constraint did_campaign_character_template_object
        check (jsonb_typeof(character_template) = 'object');
    end if;
end
$$;

-- Keep the corrected Phase 2 owner/member read rule. This also makes the
-- migration safe for a database that was created before hotfix 01.
drop policy if exists did_campaigns_select on public.campaigns;
create policy did_campaigns_select
on public.campaigns for select
to authenticated
using (
    owner_user_id = auth.uid()
    or private.did_is_campaign_member(id, auth.uid())
);

-- Phase 3 creates a campaign with its template in the same INSERT, and the DM
-- can later edit the campaign's Creation Rules. RLS still limits campaign
-- updates to owner_user_id = auth.uid().
grant insert (name, character_template)
on public.campaigns
to authenticated;

grant update (name, active, character_template)
on public.campaigns
to authenticated;

-- Preserve the Phase 2 upsert privileges as part of the canonical migration.
grant update (campaign_id, character_id, display_name, active)
on public.campaign_characters
to authenticated;

grant update (campaign_character_id, state)
on public.character_state
to authenticated;

commit;
