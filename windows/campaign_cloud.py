from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


DEFAULT_TIMEOUT_SECONDS = 15
SESSION_FILENAME = "campaign_session.json"
LINKS_FILENAME = "campaign_links.json"


class CampaignCloudError(RuntimeError):
    pass


def _json_load(path: Path, default=None):
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError) as error:
        raise CampaignCloudError(f"Could not read {path.name}: {error}") from error


def _json_write(path: Path, value):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        temporary.replace(path)
    except OSError as error:
        raise CampaignCloudError(f"Could not write {path.name}: {error}") from error


def _default_user_data_dir():
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "DID Character Sheet"
    return Path.home() / ".did_character_sheet"


def _nested_supabase_config(raw):
    if not isinstance(raw, dict):
        return {}
    nested = raw.get("supabase")
    return nested if isinstance(nested, dict) else {}


def _first_text(*values):
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _decode_jwt_payload(token):
    token = str(token or "").strip()
    pieces = token.split(".")
    if len(pieces) != 3:
        return {}
    try:
        payload = pieces[1] + "=" * (-len(pieces[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        value = json.loads(decoded.decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _validate_public_key(key):
    key = str(key or "").strip()
    if not key:
        raise CampaignCloudError("Supabase publishable/anon key is missing")

    if key.startswith("sb_secret_"):
        raise CampaignCloudError(
            "Refusing to use a Supabase secret key in the desktop app. "
            "Use the publishable/anon key instead."
        )

    payload = _decode_jwt_payload(key)
    if str(payload.get("role") or "").strip().lower() == "service_role":
        raise CampaignCloudError(
            "Refusing to use a Supabase service_role key in the desktop app. "
            "Use the publishable/anon key instead."
        )

    return key


def load_campaign_cloud_config(app_dir=None):
    """Load the existing Supabase project config without duplicating secrets.

    campaign_config.json is preferred. If it does not exist, the loader also
    understands the existing suggestions_config.json used by the Improvement
    Editor, so Phase 2 can reuse the same Supabase project.
    """
    root = Path(app_dir or Path.cwd())
    candidates = [
        root / "campaign_config.json",
        root / "suggestions_config.json",
    ]

    config_path = None
    raw = None
    for candidate in candidates:
        if candidate.is_file():
            config_path = candidate
            raw = _json_load(candidate, default={})
            break

    if config_path is None:
        raise CampaignCloudError(
            "No Supabase configuration was found. Expected campaign_config.json "
            "or the existing suggestions_config.json beside the app."
        )

    nested = _nested_supabase_config(raw)
    url = _first_text(
        raw.get("supabase_url"),
        raw.get("project_url"),
        raw.get("url"),
        nested.get("supabase_url"),
        nested.get("project_url"),
        nested.get("url"),
    ).rstrip("/")

    key = _first_text(
        raw.get("supabase_publishable_key"),
        raw.get("publishable_key"),
        raw.get("supabase_anon_key"),
        raw.get("anon_key"),
        raw.get("supabase_key"),
        raw.get("key"),
        nested.get("supabase_publishable_key"),
        nested.get("publishable_key"),
        nested.get("supabase_anon_key"),
        nested.get("anon_key"),
        nested.get("supabase_key"),
        nested.get("key"),
    )

    if not url.startswith("https://"):
        raise CampaignCloudError(
            f"Supabase URL in {config_path.name} must start with https://"
        )

    return {
        "url": url,
        "key": _validate_public_key(key),
        "source": str(config_path),
    }


class CampaignLinkStore:
    def __init__(self, user_data_dir=None):
        self.user_data_dir = Path(user_data_dir or _default_user_data_dir())
        self.path = self.user_data_dir / LINKS_FILENAME
        self._lock = threading.RLock()

    def all_links(self):
        with self._lock:
            raw = _json_load(self.path, default={})
            if not isinstance(raw, dict):
                return {}
            links = raw.get("characters", raw)
            return links if isinstance(links, dict) else {}

    def get(self, character_id):
        return self.all_links().get(str(character_id or "").strip())

    def set(self, character_id, link):
        character_id = str(character_id or "").strip()
        if not character_id:
            raise CampaignCloudError("Character has no stable ID")
        with self._lock:
            links = self.all_links()
            links[character_id] = dict(link or {})
            _json_write(self.path, {"characters": links})

    def remove(self, character_id):
        character_id = str(character_id or "").strip()
        with self._lock:
            links = self.all_links()
            removed = links.pop(character_id, None)
            _json_write(self.path, {"characters": links})
            return removed is not None


class CampaignCloudClient:
    """Small stdlib-only Supabase client for DID campaign sharing.

    The client uses Supabase anonymous Auth, so players do not need to create
    an email/password account. The resulting refresh token is stored only in
    the user's AppData folder, never in .didchar files or the project folder.
    """

    def __init__(
        self,
        app_dir=None,
        user_data_dir=None,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        config=None,
    ):
        self.app_dir = Path(app_dir or Path.cwd())
        self.user_data_dir = Path(user_data_dir or _default_user_data_dir())
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.timeout = int(timeout)
        self.config = dict(config or load_campaign_cloud_config(self.app_dir))
        self.url = str(self.config["url"]).rstrip("/")
        self.key = _validate_public_key(self.config["key"])
        self.session_path = self.user_data_dir / SESSION_FILENAME
        self.links = CampaignLinkStore(self.user_data_dir)
        self._session = None

    # ------------------------------------------------------------
    # HTTP / Auth
    # ------------------------------------------------------------

    def _request_json(
        self,
        method,
        path,
        body=None,
        query=None,
        authenticated=True,
        prefer=None,
    ):
        if not path.startswith("/"):
            path = "/" + path

        query_string = urllib.parse.urlencode(query or {}, doseq=True, safe=",")
        request_url = self.url + path
        if query_string:
            request_url += "?" + query_string

        headers = {
            "apikey": self.key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        if authenticated:
            session = self.ensure_session()
            headers["Authorization"] = f"Bearer {session['access_token']}"

        if prefer:
            headers["Prefer"] = prefer

        encoded = None
        if body is not None:
            encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")

        request = urllib.request.Request(
            request_url,
            data=encoded,
            headers=headers,
            method=str(method).upper(),
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = response.read()
                if not payload:
                    return None
                return json.loads(payload.decode("utf-8"))
        except urllib.error.HTTPError as error:
            try:
                payload = error.read().decode("utf-8", errors="replace")
                parsed = json.loads(payload) if payload else {}
                message = (
                    parsed.get("message")
                    or parsed.get("msg")
                    or parsed.get("error_description")
                    or parsed.get("error")
                    or payload
                )
            except Exception:
                message = str(error)
            raise CampaignCloudError(
                f"Supabase request failed ({error.code}): {message}"
            ) from error
        except urllib.error.URLError as error:
            raise CampaignCloudError(f"Could not reach Supabase: {error.reason}") from error
        except (OSError, json.JSONDecodeError) as error:
            raise CampaignCloudError(f"Invalid Supabase response: {error}") from error

    def _normalise_auth_response(self, raw):
        if not isinstance(raw, dict):
            raise CampaignCloudError("Supabase Auth returned an invalid response")

        session = raw.get("session") if isinstance(raw.get("session"), dict) else raw
        user = raw.get("user") if isinstance(raw.get("user"), dict) else session.get("user")
        user = user if isinstance(user, dict) else {}

        access_token = str(session.get("access_token") or "").strip()
        refresh_token = str(session.get("refresh_token") or "").strip()
        if not access_token or not refresh_token:
            raise CampaignCloudError("Supabase Auth did not return a usable session")

        expires_at = session.get("expires_at")
        if expires_at is None:
            expires_in = int(session.get("expires_in") or 3600)
            expires_at = int(time.time()) + expires_in

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "expires_at": int(expires_at),
            "user_id": str(user.get("id") or "").strip(),
            "is_anonymous": bool(user.get("is_anonymous", True)),
        }

    def _save_session(self, session):
        self._session = dict(session)
        _json_write(self.session_path, self._session)
        return self._session

    def _load_session(self):
        if self._session is not None:
            return dict(self._session)
        raw = _json_load(self.session_path, default=None)
        if isinstance(raw, dict):
            self._session = raw
            return dict(raw)
        return None

    def sign_in_anonymously(self):
        raw = self._request_json(
            "POST",
            "/auth/v1/signup",
            body={
                "data": {"application": "did_character_sheet"},
                "gotrue_meta_security": {"captcha_token": None},
            },
            authenticated=False,
        )
        return self._save_session(self._normalise_auth_response(raw))

    def refresh_session(self, refresh_token=None):
        current = self._load_session() or {}
        refresh_token = str(refresh_token or current.get("refresh_token") or "").strip()
        if not refresh_token:
            raise CampaignCloudError("No campaign refresh token is available")

        raw = self._request_json(
            "POST",
            "/auth/v1/token",
            query={"grant_type": "refresh_token"},
            body={"refresh_token": refresh_token},
            authenticated=False,
        )
        return self._save_session(self._normalise_auth_response(raw))

    def ensure_session(self):
        session = self._load_session()
        if session:
            expires_at = int(session.get("expires_at") or 0)
            if session.get("access_token") and expires_at > int(time.time()) + 90:
                return session

            refresh_token = str(session.get("refresh_token") or "").strip()
            if not refresh_token:
                raise CampaignCloudError(
                    "The saved campaign identity is incomplete. DID will not create a new "
                    "anonymous identity automatically because that could make existing "
                    "campaigns appear to disappear."
                )

            try:
                return self.refresh_session(refresh_token)
            except CampaignCloudError as error:
                # Never silently replace an established anonymous identity. Campaign
                # ownership is tied to the Supabase Auth user ID, so signing up again
                # would produce a different user and RLS would correctly hide the old
                # campaigns. Preserve the saved identity and surface the real problem.
                self._session = dict(session)
                raise CampaignCloudError(
                    "DID could not refresh the saved campaign identity. Your campaign "
                    "data has not been deleted, and DID will not create a replacement "
                    "identity automatically. Check the connection and try again."
                ) from error

        # First use only: there is no prior campaign identity to preserve.
        return self.sign_in_anonymously()

    @property
    def user_id(self):
        return str(self.ensure_session().get("user_id") or "").strip()


    # ------------------------------------------------------------
    # Official Discord service
    # ------------------------------------------------------------

    def invoke_edge_function(self, function_name, body=None):
        function_name = str(function_name or "").strip()
        if not function_name:
            raise CampaignCloudError("Edge Function name is required")
        return self._request_json(
            "POST",
            f"/functions/v1/{function_name}",
            body=dict(body or {}),
        )

    def discord_service_config(self):
        raw = self.invoke_edge_function("did-discord", {"action": "config"})
        if not isinstance(raw, dict):
            return {}
        result = dict(raw)
        # Discord sends application interactions to this small public entry
        # endpoint. It proxies to the central DID service and records Discord's
        # signed endpoint-verification PING before any campaign can be linked.
        result["endpoint_url"] = f"{self.url}/functions/v1/did-discord-entry"
        verified = bool(result.get("endpoint_verified", result.get("endpoint_ready")))
        result["endpoint_verified"] = verified
        result["endpoint_ready"] = verified
        result["configured"] = bool(result.get("credentials_ready") and verified)
        return result

    def bootstrap_official_discord(self, application_id, public_key, bot_token):
        result = self._request_json(
            "POST",
            "/rest/v1/rpc/did_bootstrap_official_discord",
            body={
                "p_application_id": str(application_id or "").strip(),
                "p_public_key": str(public_key or "").strip(),
                "p_bot_token": str(bot_token or "").strip(),
            },
        )
        return bool(result)

    def register_official_discord_commands(self):
        raw = self.invoke_edge_function("did-discord", {"action": "register_commands"})
        if isinstance(raw, dict) and raw.get("error"):
            raise CampaignCloudError(str(raw.get("error")))
        return raw if isinstance(raw, dict) else {}

    def confirm_official_discord_endpoint(self):
        result = self._request_json(
            "POST",
            "/rest/v1/rpc/did_confirm_official_discord_endpoint",
            body={},
        )
        return bool(result)

    def create_discord_connect_code(self, campaign_id):
        campaign_id = str(campaign_id or "").strip()
        rows = self._request_json(
            "POST",
            "/rest/v1/rpc/did_create_discord_connect_token",
            body={"p_campaign_id": campaign_id},
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("Could not create a Discord connection code")
        return rows[0]

    def get_discord_connection(self, campaign_id):
        campaign_id = str(campaign_id or "").strip()
        rows = self._request_json(
            "POST",
            "/rest/v1/rpc/did_get_discord_connection",
            body={"p_campaign_id": campaign_id},
        )
        return rows[0] if isinstance(rows, list) and rows else None

    def disconnect_discord_campaign(self, campaign_id):
        campaign_id = str(campaign_id or "").strip()
        return bool(self._request_json(
            "POST",
            "/rest/v1/rpc/did_disconnect_discord_campaign",
            body={"p_campaign_id": campaign_id},
        ))

    def notify_discord_roll(self, campaign_id, event_id):
        return self.invoke_edge_function("did-discord", {
            "action": "notify_roll",
            "campaign_id": str(campaign_id or "").strip(),
            "event_id": str(event_id or "").strip(),
        })

    def notify_discord_session(self, campaign_id, event, session):
        return self.invoke_edge_function("did-discord", {
            "action": "notify_session",
            "campaign_id": str(campaign_id or "").strip(),
            "event": str(event or "").strip(),
            "session": dict(session or {}),
        })

    # ------------------------------------------------------------
    # Campaigns
    # ------------------------------------------------------------

    def create_campaign(self, name):
        name = str(name or "").strip()
        if not name:
            raise CampaignCloudError("Campaign name cannot be empty")
        if len(name) > 100:
            raise CampaignCloudError("Campaign name is too long")

        rows = self._request_json(
            "POST",
            "/rest/v1/campaigns",
            query={"select": "id,name,invite_code,created_at,owner_user_id"},
            body={"name": name},
            prefer="return=representation",
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("Campaign was created but no record was returned")
        return rows[0]

    def join_campaign(self, invite_code, display_name="Player"):
        invite_code = str(invite_code or "").strip().upper().replace(" ", "")
        display_name = str(display_name or "Player").strip() or "Player"
        if not invite_code:
            raise CampaignCloudError("Campaign invite code cannot be empty")
        if len(display_name) > 80:
            raise CampaignCloudError("Player display name is too long")

        rows = self._request_json(
            "POST",
            "/rest/v1/rpc/did_join_campaign",
            body={
                "p_invite_code": invite_code,
                "p_display_name": display_name,
            },
        )
        if not isinstance(rows, list) or not rows:
            raise CampaignCloudError("Campaign invite code was not found")
        return rows[0]

    def list_my_campaigns(self):
        rows = self._request_json(
            "GET",
            "/rest/v1/campaigns",
            query={
                "select": "id,name,invite_code,created_at,owner_user_id",
                "order": "created_at.desc",
            },
        )
        return rows if isinstance(rows, list) else []

    # ------------------------------------------------------------
    # Character links / state
    # ------------------------------------------------------------

    def link_character(self, campaign_id, shared_state, remember=True, *, creation_claim=None):
        """Admit a compliant character via the authenticated database RPC.

        A local rules check is only for feedback; the server independently
        compares the creation claim with its current campaign template.
        The client MUST NOT write public.campaign_characters directly.
        """
        if not isinstance(shared_state, dict) or not isinstance(creation_claim, dict):
            raise CampaignCloudError("Character state and creation-rule details are required")
        character_id = str(shared_state.get("character_id") or "").strip()
        character_name = str(shared_state.get("name") or "").strip()
        campaign_id = str(campaign_id or "").strip()
        if not campaign_id or not character_id or not character_name:
            raise CampaignCloudError("Campaign, character ID and name are required")

        # The response is created atomically with its first shared snapshot.
        record = self._request_json(
            "POST", "/rest/v1/rpc/did_admit_compliant_character",
            body={
                "p_campaign_id": campaign_id,
                "p_shared_state": shared_state,
                "p_creation": creation_claim,
            },
        )
        if isinstance(record, list):
            record = record[0] if record else None
        if not isinstance(record, dict) or not record.get("id"):
            raise CampaignCloudError("The server did not approve this character for the campaign")
        if str(record.get("campaign_id") or "") != campaign_id:
            raise CampaignCloudError("The server returned an unexpected campaign link")
        if remember:
            self.links.set(character_id, {
                "campaign_id": campaign_id,
                "campaign_character_id": str(record["id"]),
                "character_name": character_name,
            })
        return record

    def get_character_link(self, character_id):
        """Only approved/active links can publish campaign data."""
        link = self.links.get(character_id)
        if isinstance(link, dict) and link.get("approval_status") in ("pending", "rejected"):
            return None
        return link

    def get_pending_character_approval(self, character_id):
        link = self.links.get(character_id)
        if isinstance(link, dict) and link.get("approval_status") in ("pending", "rejected"):
            return link
        return None

    def request_character_approval(self, campaign_id, shared_state, mismatches):
        """Persist a private DM request; do not publish an active character."""
        character_id = str(shared_state.get("character_id") or "").strip()
        if not character_id or not mismatches:
            raise CampaignCloudError("A character and rule differences are required")
        response = self._request_json(
            "POST", "/rest/v1/rpc/did_request_character_approval",
            body={
                "p_campaign_id": str(campaign_id),
                "p_character_id": character_id,
                "p_display_name": str(shared_state.get("name") or "Character"),
                "p_shared_state": shared_state,
                "p_mismatches": list(mismatches),
            },
        )
        if not isinstance(response, dict) or not response.get("id"):
            raise CampaignCloudError("The DM approval request was not saved")
        if response.get("status") == "approved" and response.get("approved_character_id"):
            self.links.set(character_id, {
                "campaign_id": str(campaign_id),
                "campaign_character_id": str(response["approved_character_id"]),
                "character_name": str(shared_state.get("name") or "Character"),
            })
        else:
            self.links.set(character_id, {
                "campaign_id": str(campaign_id),
                "request_id": str(response["id"]),
                "character_name": str(shared_state.get("name") or "Character"),
                "approval_status": "pending",
            })
        return response

    def cancel_character_approval(self, request_id):
        if not request_id:
            return False
        result = self._request_json(
            "POST", "/rest/v1/rpc/did_cancel_character_approval",
            body={"p_request_id": str(request_id)},
        )
        return bool(result)

    def list_pending_character_approvals(self, campaign_id):
        rows = self._request_json(
            "GET", "/rest/v1/campaign_character_approval_requests",
            query={
                "campaign_id": f"eq.{campaign_id}", "status": "eq.pending",
                "select": "id,campaign_id,character_id,display_name,mismatch_details,created_at",
                "order": "created_at.asc",
            },
        )
        return rows if isinstance(rows, list) else []

    def decide_character_approval(self, request_id, approve):
        result = self._request_json(
            "POST", "/rest/v1/rpc/did_decide_character_approval",
            body={"p_request_id": str(request_id), "p_approve": bool(approve)},
        )
        if not isinstance(result, dict) or result.get("status") not in {"approved", "rejected"}:
            raise CampaignCloudError("DM decision was not recorded")
        return result

    def refresh_pending_character_approval(self, character_id):
        """Check an outstanding request; activate only on explicit DM approval."""
        pending = self.get_pending_character_approval(character_id)
        if not isinstance(pending, dict) or pending.get("approval_status") != "pending":
            return pending
        request_id = str(pending.get("request_id") or "")
        if not request_id:
            return pending
        rows = self._request_json(
            "GET", "/rest/v1/campaign_character_approval_requests",
            query={
                "id": f"eq.{request_id}",
                "select": "id,status,approved_character_id,campaign_id,display_name",
                "limit": "1",
            },
        )
        if not isinstance(rows, list) or not rows:
            # An admin may have deleted the request. Do not silently activate.
            return pending
        result = rows[0]
        status = str(result.get("status") or "")
        if status == "approved" and result.get("approved_character_id"):
            active = {
                "campaign_id": str(result["campaign_id"]),
                "campaign_character_id": str(result["approved_character_id"]),
                "character_name": str(result.get("display_name") or pending.get("character_name") or "Character"),
            }
            self.links.set(character_id, active)
            return dict(active, approval_status="approved")
        if status == "rejected":
            changed = dict(pending, approval_status="rejected")
            self.links.set(character_id, changed)
            return changed
        return pending

    def unlink_local_character(self, character_id):
        return self.links.remove(character_id)

    def upload_character_state(self, campaign_character_id, shared_state):
        if not isinstance(shared_state, dict):
            raise CampaignCloudError("Shared character state must be a dictionary")
        rows = self._request_json(
            "POST",
            "/rest/v1/character_state",
            query={
                "on_conflict": "campaign_character_id",
                "select": "campaign_character_id,updated_at",
            },
            body={
                "campaign_character_id": str(campaign_character_id),
                "state": shared_state,
            },
            prefer="resolution=merge-duplicates,return=representation",
        )
        return rows[0] if isinstance(rows, list) and rows else None

    def sync_linked_character(self, shared_state):
        if not isinstance(shared_state, dict):
            raise CampaignCloudError("Shared character state must be a dictionary")
        character_id = str(shared_state.get("character_id") or "").strip()
        link = self.get_character_link(character_id)
        if not isinstance(link, dict):
            raise CampaignCloudError("This character is not linked to a campaign")
        self.upload_character_state(link["campaign_character_id"], shared_state)
        return link

    # ------------------------------------------------------------
    # Rolls
    # ------------------------------------------------------------

    def upload_roll_event(self, campaign_character_id, event):
        if not isinstance(event, dict):
            raise CampaignCloudError("Roll event must be a dictionary")
        event_id = str(event.get("event_id") or "").strip()
        rolled_utc = str(event.get("rolled_utc") or "").strip()
        if not event_id or not rolled_utc:
            raise CampaignCloudError("Roll event ID and timestamp are required")

        rows = self._request_json(
            "POST",
            "/rest/v1/campaign_rolls",
            query={
                "on_conflict": "event_id",
                "select": "event_id,campaign_character_id,rolled_at",
            },
            body={
                "event_id": event_id,
                "campaign_character_id": str(campaign_character_id),
                "rolled_at": rolled_utc,
                "event": event,
            },
            prefer="resolution=ignore-duplicates,return=representation",
        )
        if isinstance(rows, list) and rows:
            return rows[0]
        # A retry of the same event can legitimately return no inserted row.
        return {
            "event_id": event_id,
            "campaign_character_id": str(campaign_character_id),
            "duplicate": True,
        }

    def upload_linked_roll_event(self, event):
        if not isinstance(event, dict):
            raise CampaignCloudError("Roll event must be a dictionary")
        character_id = str(event.get("character_id") or "").strip()
        link = self.get_character_link(character_id)
        if not isinstance(link, dict):
            raise CampaignCloudError("This character is not linked to a campaign")
        result = self.upload_roll_event(link["campaign_character_id"], event)
        # Discord notifications are supplemental. A temporary Discord/network
        # problem must never turn a successful campaign roll upload into a
        # failed dice roll. The server also checks that this event actually
        # reached the player-safe party_session_rolls feed before posting it.
        if not result.get("duplicate"):
            try:
                self.notify_discord_roll(link.get("campaign_id"), event.get("event_id"))
            except Exception:
                pass
        return result

    # ------------------------------------------------------------
    # DM/read-side helpers for the later dashboard
    # ------------------------------------------------------------

    def list_campaign_characters(self, campaign_id):
        rows = self._request_json(
            "GET",
            "/rest/v1/campaign_characters",
            query={
                "campaign_id": f"eq.{campaign_id}",
                "active": "eq.true",
                "select": "id,campaign_id,character_id,display_name,active,created_at,updated_at,character_state(state,updated_at)",
                "order": "created_at.asc",
            },
        )
        return rows if isinstance(rows, list) else []

    def list_recent_rolls(self, campaign_id, limit=100):
        limit = max(1, min(500, int(limit)))
        rows = self._request_json(
            "GET",
            "/rest/v1/campaign_rolls",
            query={
                "campaign_characters.campaign_id": f"eq.{campaign_id}",
                "select": "event_id,rolled_at,event,campaign_character_id,campaign_characters!inner(campaign_id,display_name)",
                "order": "rolled_at.desc",
                "limit": str(limit),
            },
        )
        return rows if isinstance(rows, list) else []
