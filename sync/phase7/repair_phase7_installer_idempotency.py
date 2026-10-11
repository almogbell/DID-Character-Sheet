from __future__ import annotations

from pathlib import Path


NEW_PATCH_FRONTEND = r'''def patch_frontend(path: Path):
    """Install the Campaign Manager / My Campaigns menu split safely.

    Phase 7 is intentionally re-runnable.  Earlier versions assumed the
    frontend still had the original single Campaign menu entry, so rerunning
    the installer after a partial/successful Phase 7 install raised
    "Could not safely locate the Campaign menu block."  Accept both the
    original state and every Phase 7 state we currently create.
    """
    original = path.read_text(encoding="utf-8")
    text = original

    campaign_import = "from campaign_ui import open_campaign_manager\n"
    player_only_import = "from campaign_role_ui import open_player_campaigns\n"
    full_role_import = (
        "from campaign_role_ui import open_dm_campaign_manager, "
        "open_player_campaigns\n"
    )

    if full_role_import not in text:
        if player_only_import in text:
            text = text.replace(player_only_import, full_role_import, 1)
        elif campaign_import in text:
            text = text.replace(campaign_import, campaign_import + full_role_import, 1)
        else:
            raise RuntimeError("Could not find the Campaign UI imports in frontend_2_8.py")

    # If My Campaigns already exists, the menu split is already installed.
    # A later Phase 7 repair redirects the DM callback directly to
    # open_dm_campaign_manager, so do not insist on the older callback text.
    already_split = (
        '"Campaign Manager..."' in text
        and '"My Campaigns..."' in text
        and "player_campaign_action" in text
        and "open_player_campaigns(self)" in text
    )

    if not already_split:
        old = '''        campaign_action = campaign_menu.addAction(
            "Campaign..."
        )
        campaign_action.triggered.connect(
            lambda _checked=False: open_campaign_manager(self)
        )

        campaign_menu.addSeparator()
'''
        old_alt = old.replace('"Campaign..."', '"Campaign Manager..."')
        new = '''        campaign_action = campaign_menu.addAction(
            "Campaign Manager..."
        )
        campaign_action.triggered.connect(
            lambda _checked=False: open_campaign_manager(self)
        )

        player_campaign_action = campaign_menu.addAction(
            "My Campaigns..."
        )
        player_campaign_action.triggered.connect(
            lambda _checked=False: open_player_campaigns(self)
        )

        campaign_menu.addSeparator()
'''
        if old in text:
            text = text.replace(old, new, 1)
        elif old_alt in text:
            text = text.replace(old_alt, new, 1)
        else:
            raise RuntimeError(
                "Could not safely locate the Campaign menu block, and the "
                "Phase 7 menu split is not present."
            )

    if text != original:
        backup_once(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False
'''


def repair():
    installer = Path(__file__).resolve().parent / "install_phase7.py"
    text = installer.read_text(encoding="utf-8")

    start = text.find("def patch_frontend(path: Path):\n")
    if start < 0:
        raise RuntimeError("Could not locate patch_frontend in install_phase7.py")
    end = text.find("\ndef patch_campaign_ui_delegate(path: Path):\n", start)
    if end < 0:
        raise RuntimeError("Could not locate patch_campaign_ui_delegate in install_phase7.py")

    current = text[start:end]
    if "Phase 7 is intentionally re-runnable" in current:
        return False

    updated = text[:start] + NEW_PATCH_FRONTEND + "\n" + text[end + 1:]
    installer.write_text(updated, encoding="utf-8")
    return True


if __name__ == "__main__":
    print(
        "Phase 7 installer idempotency repair: PASS"
        if repair()
        else "Phase 7 installer idempotency repair: already fixed"
    )
