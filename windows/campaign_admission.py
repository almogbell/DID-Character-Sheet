"""Character admission to a campaign, including DM exceptions to creation rules.

Pure coordination code: no PySide6 import. The invitation joins the *player*;
noncompliant characters require a separate DM decision before becoming linked.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AdmissionResult:
    status: str  # linked | approval_pending | linked_elsewhere
    record_id: str = ""
    mismatches: tuple[str, ...] = ()
    request_id: str = ""


def creation_claim_from_character(character) -> dict:
    """The minimum metadata needed by the server to evaluate current rules.

    This is a client-provided claim, not cryptographic proof of a .didchar file.
    The server independently checks its campaign template and shared values.
    """
    return {
        "active": bool(getattr(character, "creation_rules_active", False)),
        "species_mode": str(getattr(character, "creation_species_mode", "normal")),
        "allow_custom_improvements": bool(getattr(character, "creation_allow_custom_improvements", True)),
        "allowed_ability_array_ids": sorted(str(s) for s in (getattr(character, "creation_allowed_ability_array_ids", None) or [])),
        "restrict_ability_dice_to_allowed_arrays": bool(getattr(character, "creation_restrict_ability_dice_to_allowed_arrays", False)),
        "improvement_mode": str(getattr(character, "creation_improvement_mode", "all")),
        "improvement_ids": sorted(str(s) for s in (getattr(character, "creation_improvement_ids", None) or [])),
        "improvement_overrides": dict(getattr(character, "creation_improvement_overrides", None) or {}),
        "template_custom_improvements": list(getattr(character, "creation_template_custom_improvements", None) or []),
        "free_heightened_ability_slots": int(getattr(character, "free_heightened_ability_slots", 2)),
    }


def admit_character(window, campaign: dict, client, shared_state: dict, *, mismatch_checker=None):
    """Submit an existing character under the campaign's rules.

    An approved existing link remains approved even if the DM later revises
    creation rules. Never make or upload an active character link while a
    rule exception is awaiting the DM's authorization.
    """
    character = getattr(window, "character", None)
    character_id = str(getattr(character, "id", "") or "").strip()
    campaign_id = str(campaign.get("id") or "").strip()
    if not character_id or not campaign_id:
        raise ValueError("A named character and campaign are required")
    active = client.get_character_link(character_id)
    if isinstance(active, dict):
        if str(active.get("campaign_id") or "") != campaign_id:
            return AdmissionResult("linked_elsewhere")
        record_id = str(active.get("campaign_character_id") or "")
        if not record_id:
            raise ValueError("Existing campaign link has no record ID")
        client.upload_character_state(record_id, shared_state)
        return AdmissionResult("linked", record_id)

    pending_getter = getattr(client, "get_pending_character_approval", None)
    pending = pending_getter(character_id) if callable(pending_getter) else None
    if isinstance(pending, dict) and str(pending.get("campaign_id") or "") != campaign_id:
        return AdmissionResult("linked_elsewhere")

    if mismatch_checker is None:
        from campaign_template import campaign_template, character_rule_mismatches
        checker = lambda current, target: character_rule_mismatches(current, campaign_template(target))
    else:
        checker = mismatch_checker
    mismatches = tuple(str(item) for item in checker(character, campaign))
    if mismatches:
        request = client.request_character_approval(campaign_id, shared_state, mismatches)
        if str(request.get("status") or "") == "approved":
            active = client.get_character_link(character_id)
            if active:
                client.upload_character_state(active["campaign_character_id"], shared_state)
                return AdmissionResult("linked", str(active["campaign_character_id"]))
            raise RuntimeError("Approved character link was not returned by the server")
        return AdmissionResult(
            "approval_pending", mismatches=mismatches,
            request_id=str(request.get("id") or ""),
        )

    # A previously pending request is not automatically approved by newly
    # compliant local edits. Its earlier DM decision may arrive later. The
    # user can re-submit a compliant character using the normal link path;
    # close the stale request first to avoid approving outdated state.
    if isinstance(pending, dict):
        # The DM may have approved between reading local state and cancelling.
        # Never override an approved server decision with a new direct link.
        result = client.refresh_pending_character_approval(character_id)
        if isinstance(result, dict) and result.get("approval_status") == "approved":
            active = client.get_character_link(character_id)
            client.upload_character_state(active["campaign_character_id"], shared_state)
            return AdmissionResult("linked", str(active["campaign_character_id"]))
        if not client.cancel_character_approval(pending.get("request_id")):
            raise RuntimeError("Could not close the pending request. Refresh and try again.")
        client.unlink_local_character(character_id)

    linked = client.link_character(
        campaign_id, shared_state, remember=True,
        creation_claim=creation_claim_from_character(character),
    )
    return AdmissionResult("linked", str(linked["id"]))
