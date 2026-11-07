"""Read-only remote verification of a locally remembered campaign character link.

Returns statuses; the caller decides when to refresh UI or clear the local link.
Never deletes a .didchar file, bypasses an offline error, or changes Supabase.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class LinkCheck:
    status: str  # active, removed, unlinked, offline
    message: str
    link: dict | None


def verify_character_link(client, character_id, campaign_id):
    """Use the exact existing link ID to avoid confusing two campaigns/characters."""
    character_id = str(character_id or '').strip()
    campaign_id = str(campaign_id or '').strip()
    if not character_id or not campaign_id:
        return LinkCheck('unlinked', 'No character or campaign selected.', None)
    link = client.get_character_link(character_id)
    if not isinstance(link, dict) or str(link.get('campaign_id') or '') != campaign_id:
        return LinkCheck('unlinked', 'Character is not linked to this campaign.', None)
    linked_id = str(link.get('campaign_character_id') or '').strip()
    if not linked_id:
        return LinkCheck('unlinked', 'Local campaign link is incomplete.', None)
    # The authenticated player can read their own row under existing RLS.
    # An empty list is interpreted only for this exact linked row, not an
    # arbitrary player or a bulk search across campaigns.
    try:
        rows = client._request_json('GET','/rest/v1/campaign_characters',query={
            'id':f'eq.{linked_id}',
            'campaign_id':f'eq.{campaign_id}',
            'owner_user_id':f'eq.{client.user_id}',
            'select':'id,campaign_id,owner_user_id,active',
            'limit':'1',
        })
    except Exception as error:
        # IMPORTANT: No mutation on failed network requests or auth errors.
        return LinkCheck('offline',f'Could not verify connection: {error}',link)
    if not isinstance(rows,list):
        return LinkCheck('offline','Unexpected response while checking campaign link.',link)
    if rows and rows[0].get('active') is True:
        return LinkCheck('active','Character is connected to the campaign.',link)
    return LinkCheck('removed','The DM removed this character from the campaign.',link)


def clear_confirmed_removed_link(client, character_id, check):
    """Forget ONLY the stale local link; leave local characters and saves alone."""
    if check.status != 'removed':
        return False
    character_id = str(character_id or '').strip()
    original = check.link or {}
    current = client.get_character_link(character_id)
    if not isinstance(current,dict):
        return False
    if (current.get('campaign_character_id') != original.get('campaign_character_id')
            or current.get('campaign_id') != original.get('campaign_id')):
        # A new link was created since the request; never remove that one.
        return False
    client.unlink_local_character(character_id)
    return True
