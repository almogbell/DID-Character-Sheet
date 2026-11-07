-- DID Character Sheet 1.0.13: authenticate and validate compliant-character
-- admission against the CURRENT server-owned campaign template.
-- Does not grant clients INSERT/UPDATE on campaign_characters.
-- Apply once to the existing DID-Suggestions Supabase project.
BEGIN;

CREATE OR REPLACE FUNCTION private.did_sorted_text_array(p_items jsonb)
RETURNS jsonb LANGUAGE sql IMMUTABLE SET search_path='' AS $$
  SELECT coalesce(jsonb_agg(v ORDER BY v), '[]'::jsonb)
  FROM jsonb_array_elements_text(
    CASE WHEN jsonb_typeof(p_items)='array' THEN p_items ELSE '[]'::jsonb END
  ) AS parts(v);
$$;

CREATE OR REPLACE FUNCTION private.did_admit_compliant_character_impl(
    p_campaign_id uuid, p_shared_state jsonb, p_creation jsonb
) RETURNS jsonb
LANGUAGE plpgsql SECURITY DEFINER SET search_path='' AS $$
DECLARE
  actor uuid := auth.uid();
  campaign_record public.campaigns%rowtype;
  rules jsonb;
  char_id text;
  char_name text;
  saved public.campaign_characters%rowtype;
  linked_id uuid;
BEGIN
  IF actor IS NULL THEN RAISE EXCEPTION 'Authentication required'; END IF;
  SELECT * INTO campaign_record FROM public.campaigns
   WHERE id=p_campaign_id FOR SHARE;
  IF campaign_record.id IS NULL OR NOT campaign_record.active THEN
    RAISE EXCEPTION 'Campaign unavailable';
  END IF;
  IF NOT private.did_is_campaign_member(p_campaign_id, actor) THEN
    RAISE EXCEPTION 'Campaign membership required';
  END IF;
  IF jsonb_typeof(p_shared_state) IS DISTINCT FROM 'object'
     OR jsonb_typeof(p_creation) IS DISTINCT FROM 'object'
     OR pg_column_size(p_shared_state)>10000000 OR pg_column_size(p_creation)>1000000 THEN
    RAISE EXCEPTION 'Invalid character submission';
  END IF;
  char_id := nullif(btrim(p_shared_state->>'character_id'), '');
  char_name := nullif(btrim(p_shared_state->>'name'), '');
  IF char_id IS NULL OR char_name IS NULL
    OR length(char_id)>200 OR length(char_name)>150
    OR lower(char_name)='unnamed character'
    OR p_shared_state->>'kind' IS DISTINCT FROM 'character_state' THEN
    RAISE EXCEPTION 'A named character with an ID is required';
  END IF;
  -- A character must never be silently moved between campaigns.
  IF EXISTS (SELECT 1 FROM public.campaign_characters cc
       WHERE cc.owner_user_id=actor AND cc.character_id=char_id
         AND cc.campaign_id<>p_campaign_id AND cc.active=true) THEN
    RAISE EXCEPTION 'Character is linked to another campaign';
  END IF;

  SELECT * INTO saved FROM public.campaign_characters cc
   WHERE cc.campaign_id=p_campaign_id AND cc.owner_user_id=actor
     AND cc.character_id=char_id FOR UPDATE;
  IF saved.id IS NOT NULL AND NOT saved.active THEN
    RAISE EXCEPTION 'Inactive character link requires DM review';
  END IF;
  IF saved.id IS NULL THEN
    -- Never silently admit a previously rejected or pending exception.
    IF EXISTS (SELECT 1 FROM public.campaign_character_approval_requests ar
        WHERE ar.campaign_id=p_campaign_id AND ar.owner_user_id=actor
          AND ar.character_id=char_id AND ar.status IN ('pending','rejected','approved')) THEN
      RAISE EXCEPTION 'Existing approval decision must be resolved by the DM';
    END IF;

    rules := coalesce(campaign_record.character_template->'rules', '{}'::jsonb);
    IF jsonb_typeof(rules) IS DISTINCT FROM 'object'
       OR p_creation->'active' IS DISTINCT FROM 'true'::jsonb
       OR p_creation->>'species_mode' IS DISTINCT FROM coalesce(rules->>'species_mode','normal')
       OR p_creation->'allow_custom_improvements' IS DISTINCT FROM coalesce(rules->'allow_custom_improvements','true'::jsonb)
       OR jsonb_typeof(p_creation->'allowed_ability_array_ids') IS DISTINCT FROM 'array'
       OR private.did_sorted_text_array(p_creation->'allowed_ability_array_ids')
          IS DISTINCT FROM private.did_sorted_text_array(rules->'allowed_ability_array_ids')
       OR p_creation->'restrict_ability_dice_to_allowed_arrays'
          IS DISTINCT FROM coalesce(rules->'restrict_ability_dice_to_allowed_arrays','false'::jsonb)
       OR p_creation->>'improvement_mode' IS DISTINCT FROM coalesce(rules->>'improvement_mode','all')
       OR jsonb_typeof(p_creation->'improvement_ids') IS DISTINCT FROM 'array'
       OR private.did_sorted_text_array(p_creation->'improvement_ids')
          IS DISTINCT FROM private.did_sorted_text_array(rules->'improvement_ids')
       OR p_creation->'improvement_overrides' IS DISTINCT FROM coalesce(rules->'improvement_overrides','{}'::jsonb)
       OR p_creation->'template_custom_improvements' IS DISTINCT FROM coalesce(rules->'template_custom_improvements','[]'::jsonb)
       OR (p_creation->>'free_heightened_ability_slots')::integer
          IS DISTINCT FROM coalesce((rules->>'free_heightened_ability_slots')::integer,2)
       OR coalesce((p_shared_state->>'level')::integer,-1) < coalesce((rules->>'level')::integer,1)
       OR (rules->'starting_hearts' IS NOT NULL AND rules->'starting_hearts' <> 'null'::jsonb
           AND coalesce((p_shared_state#>>'{resources,hearts,max}')::integer,-1)
             < (rules->>'starting_hearts')::integer)
       OR (rules->'starting_at' IS NOT NULL AND rules->'starting_at' <> 'null'::jsonb
           AND coalesce((p_shared_state#>>'{resources,adversity_tokens,max}')::integer,-1)
             < (rules->>'starting_at')::integer)
    THEN
      RAISE EXCEPTION 'Character does not meet current campaign rules; request DM approval';
    END IF;
    INSERT INTO public.campaign_characters(campaign_id,owner_user_id,character_id,display_name,active)
      VALUES(p_campaign_id,actor,char_id,char_name,true)
      ON CONFLICT(campaign_id,owner_user_id,character_id) DO NOTHING
      RETURNING id INTO linked_id;
    IF linked_id IS NULL THEN
      RAISE EXCEPTION 'Character link changed during submission; please retry';
    END IF;
  ELSE
    -- Already admitted/active characters may keep updating after rules change.
    linked_id := saved.id;
    UPDATE public.campaign_characters SET display_name=char_name
      WHERE id=linked_id;
  END IF;

  INSERT INTO public.character_state(campaign_character_id,state)
    VALUES(linked_id,p_shared_state)
    ON CONFLICT(campaign_character_id) DO UPDATE SET state=excluded.state;

  RETURN jsonb_build_object('id',linked_id,'campaign_id',p_campaign_id,
     'character_id',char_id,'display_name',char_name,'active',true);
END;
$$;

CREATE OR REPLACE FUNCTION public.did_admit_compliant_character(
    p_campaign_id uuid, p_shared_state jsonb, p_creation jsonb
) RETURNS jsonb LANGUAGE sql SECURITY INVOKER SET search_path='' AS $$
 SELECT private.did_admit_compliant_character_impl(p_campaign_id,p_shared_state,p_creation);
$$;

REVOKE ALL ON FUNCTION private.did_sorted_text_array(jsonb) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION private.did_admit_compliant_character_impl(uuid,jsonb,jsonb) FROM PUBLIC, anon;
REVOKE ALL ON FUNCTION public.did_admit_compliant_character(uuid,jsonb,jsonb) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION private.did_admit_compliant_character_impl(uuid,jsonb,jsonb) TO authenticated;
GRANT EXECUTE ON FUNCTION public.did_admit_compliant_character(uuid,jsonb,jsonb) TO authenticated;
REVOKE INSERT,UPDATE ON public.campaign_characters FROM authenticated,anon,PUBLIC;
COMMIT;
