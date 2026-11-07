"""Invitation-code campaign join and automatic character publication.

A join is a remote membership operation.  Publication is a separate cloud
operation, but it is now automatically attempted by the same Join action.
Only an explicitly named, rules-compliant character is published immediately.
An existing character with mismatches is submitted privately for DM approval.  A blank
starter character is NEVER silently sent to a campaign.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JoinPublication:
    campaign: dict
    status: str  # linked, needs_character, linked_elsewhere
    character_name: str = ""
    warning: str = ""
    mismatches: tuple[str, ...] = ()


class JoinedButCharacterNotPublished(RuntimeError):
    """Membership succeeded but the character upload failed. Safe to retry."""

    def __init__(self, campaign: dict, reason: Exception):
        self.campaign = campaign
        super().__init__(
            "You joined the campaign, but your character could not be sent to "
            f"the DM. Please retry joining or use Save to Campaign.\n\n{reason}"
        )


def join_campaign_and_publish(
    window, service, client, invite_code, display_name, *,
    shared_state_builder=None, party_state_builder=None,
    party_state_uploader=None, connection_restorer=None, mismatch_checker=None,
):
    """Join the campaign AND immediately publish the active character if valid.

    Optional callables allow transport-independent regression testing.  The
    real production builders respect DM and party privacy settings.  This
    never imports or copies a different account's .didchar file.
    """
    campaign = service.join_campaign(invite_code, display_name)
    campaign_id = str(campaign.get("id") or "").strip()
    if not campaign_id:
        raise JoinedButCharacterNotPublished(campaign, ValueError("Campaign ID missing from join response"))

    character = getattr(window, "character", None)
    character_id = str(getattr(character, "id", "") or "").strip()
    name = str(getattr(character, "name", "") or "").strip()
    if not character_id or not name or name.casefold() == "unnamed character":
        return JoinPublication(campaign, "needs_character")

    try:
        if shared_state_builder is None:
            from campaign_privacy import build_window_shared_state as shared_state_builder
        if party_state_builder is None:
            from campaign_party import build_window_party_state as party_state_builder
        if party_state_uploader is None:
            from campaign_party import upload_party_state as party_state_uploader
        if connection_restorer is None:
            from campaign_runtime import restore_campaign_connection as connection_restorer

        from campaign_admission import admit_character
        shared = shared_state_builder(window, campaign_id=campaign_id)
        admission = admit_character(window, campaign, client, shared, mismatch_checker=mismatch_checker)
        if admission.status == "linked_elsewhere":
            return JoinPublication(campaign, "linked_elsewhere", name)
        if admission.status == "approval_pending":
            return JoinPublication(campaign, "approval_pending", name, mismatches=admission.mismatches)
        record_id = admission.record_id
        connection_restorer(window)
    except Exception as error:
        raise JoinedButCharacterNotPublished(campaign, error) from error

    warning = ""
    try:
        party_state = party_state_builder(window, campaign_id=campaign_id)
        party_state_uploader(client, campaign_id, record_id, party_state)
    except Exception as error:
        # The DM-safe character upload has already succeeded.  Keep that link;
        # do not report full success for party sharing or destroy the record.
        warning = f"The character reached the DM, but Party Dashboard sharing failed: {error}"

    return JoinPublication(campaign, "linked", name, warning)
