"""Local policy for campaign-controlled character progression tools.

The campaign link is stored in AppData, not in the current UI page; therefore
returning to the sheet does not re-enable GM-only edits. No network calls.
Standalone creation-rule templates are deliberately not considered campaigns.
"""
from __future__ import annotations


def campaign_tools_locked(character_id, *, pending=None, link=None) -> bool:
    """Return True for campaign-linked or in-progress campaign characters."""
    character_id = str(character_id or "").strip()
    if not character_id:
        return False
    if isinstance(pending, dict) and (
        str(pending.get("character_id") or "").strip() == character_id
        and str(pending.get("campaign_id") or "").strip()
    ):
        return True
    if not isinstance(link, dict):
        return False
    if not str(link.get("campaign_id") or "").strip():
        return False
    # An explicitly removed/unlinked campaign should not indefinitely lock
    # the character when the local record has not yet been pruned.
    if str(link.get("status") or "").lower() in ("removed", "unlinked"):
        return False
    return True


def window_campaign_tools_locked(window) -> bool:
    character_id = str(getattr(getattr(window, "character", None), "id", "") or "").strip()
    if not character_id:
        return False
    pending = getattr(window, "_pending_campaign_character", None)
    if campaign_tools_locked(character_id, pending=pending):
        return True
    from campaign_cloud import CampaignLinkStore
    client = getattr(window, "_campaign_cloud_client", None)
    user_data_dir = getattr(client, "user_data_dir", None)
    try:
        link = CampaignLinkStore(user_data_dir=user_data_dir).get(character_id)
    except (OSError, ValueError, RuntimeError):
        # A corrupt or locked local link store should not break the Tools menu.
        return False
    return campaign_tools_locked(character_id, link=link)
