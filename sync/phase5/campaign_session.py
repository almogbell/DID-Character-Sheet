from __future__ import annotations

from campaign_cloud import CampaignCloudError


class CampaignSessionService:
    """Small Phase 5 client for session status and player roll-sharing controls."""

    def __init__(self, client):
        self.client = client

    def list_sessions(self, campaign_id, limit=50):
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id:
            return []
        limit = max(1, min(200, int(limit)))
        rows = self.client._request_json(
            "GET",
            "/rest/v1/campaign_sessions",
            query={
                "campaign_id": f"eq.{campaign_id}",
                "select": "id,campaign_id,session_number,started_at,ended_at,started_by_user_id",
                "order": "started_at.desc",
                "limit": str(limit),
            },
        )
        return rows if isinstance(rows, list) else []

    def active_session(self, campaign_id):
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id:
            return None
        rows = self.client._request_json(
            "GET",
            "/rest/v1/campaign_sessions",
            query={
                "campaign_id": f"eq.{campaign_id}",
                "ended_at": "is.null",
                "select": "id,campaign_id,session_number,started_at,ended_at,started_by_user_id",
                "order": "started_at.desc",
                "limit": "1",
            },
        )
        return rows[0] if isinstance(rows, list) and rows else None

    def start_session(self, campaign_id):
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id:
            raise CampaignCloudError("Campaign ID is required")
        rows = self.client._request_json(
            "POST",
            "/rest/v1/rpc/did_start_session",
            body={"p_campaign_id": campaign_id},
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("The session could not be started")
        return rows[0]

    def end_session(self, campaign_id):
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id:
            raise CampaignCloudError("Campaign ID is required")
        rows = self.client._request_json(
            "POST",
            "/rest/v1/rpc/did_end_session",
            body={"p_campaign_id": campaign_id},
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("The session could not be ended")
        return rows[0]

    def get_roll_sharing(self, campaign_character_id):
        campaign_character_id = str(campaign_character_id or "").strip()
        if not campaign_character_id:
            return True
        rows = self.client._request_json(
            "GET",
            "/rest/v1/campaign_characters",
            query={
                "id": f"eq.{campaign_character_id}",
                "select": "id,share_session_rolls",
                "limit": "1",
            },
        )
        if not isinstance(rows, list) or not rows:
            return True
        return bool(rows[0].get("share_session_rolls", True))

    def set_roll_sharing(self, campaign_character_id, enabled):
        campaign_character_id = str(campaign_character_id or "").strip()
        if not campaign_character_id:
            raise CampaignCloudError("Campaign character ID is required")
        rows = self.client._request_json(
            "PATCH",
            "/rest/v1/campaign_characters",
            query={
                "id": f"eq.{campaign_character_id}",
                "select": "id,share_session_rolls",
            },
            body={"share_session_rolls": bool(enabled)},
            prefer="return=representation",
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("Could not update session roll sharing")
        return rows[0]

    def list_snapshots(self, session_id):
        session_id = str(session_id or "").strip()
        if not session_id:
            return []
        rows = self.client._request_json(
            "GET",
            "/rest/v1/session_snapshots",
            query={
                "session_id": f"eq.{session_id}",
                "select": "id,session_id,campaign_character_id,snapshot_kind,captured_at,state",
                "order": "captured_at.asc",
            },
        )
        return rows if isinstance(rows, list) else []
