-- DID Character Sheet — Phase 2 hotfix 01
-- Fix campaign creation with PostgREST return=representation.
--
-- The campaign creator owns the row immediately, before/independent of the
-- automatic campaign_members trigger. Allow the owner to SELECT their own
-- campaign directly; campaign members continue to be readable through the
-- existing membership helper.

begin;

drop policy if exists did_campaigns_select on public.campaigns;

create policy did_campaigns_select
on public.campaigns for select
to authenticated
using (
    owner_user_id = auth.uid()
    or private.did_is_campaign_member(id, auth.uid())
);

commit;
