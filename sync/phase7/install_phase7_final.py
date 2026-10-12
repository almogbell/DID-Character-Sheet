from __future__ import annotations

import runpy
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent

    # campaign_role_ui.py in the packaged Phase 7 source needs one small
    # preflight syntax repair before install_phase7.py copies/compiles it.
    print("Phase 7 packaged UI preflight...")
    runpy.run_path(str(here / "repair_phase7_packaged.py"), run_name="__main__")

    # Re-running Phase 7 after a partial or successful install must be safe.
    print("\nPhase 7 installer idempotency preflight...")
    runpy.run_path(
        str(here / "repair_phase7_installer_idempotency.py"),
        run_name="__main__",
    )

    # Put the new live-dashboard files in the project before the base installer
    # runs test_phase7.py. The base installer then copies the updated HTML/CSS.
    print("\nPhase 7 live Party Dashboard assets...")
    runpy.run_path(str(here / "install_phase7_live_assets.py"), run_name="__main__")

    print("\nPhase 7 base install...")
    runpy.run_path(str(here / "install_phase7.py"), run_name="__main__")

    # Direct PostgREST upserts on party_character_state produced a PostgreSQL
    # table-permission 403 on some Supabase/PostgREST versions. Use the
    # owner-checked RPC installed by campaign_supabase_phase7_hotfix_02.sql.
    print("\nPhase 7 Party state RPC client repair...")
    runpy.run_path(str(here / "repair_phase7_party_state_rpc.py"), run_name="__main__")

    print("\nPhase 7 UI repair v2...")
    runpy.run_path(str(here / "repair_phase7_ui_v2.py"), run_name="__main__")

    print("\nPhase 7 UI repair v3...")
    runpy.run_path(str(here / "repair_phase7_ui_v3.py"), run_name="__main__")

    print("\nPhase 7 UI repair v4...")
    runpy.run_path(str(here / "repair_phase7_ui_v4.py"), run_name="__main__")

    # v5 made the visual sizing worse. Explicitly restore the exact UI state
    # from immediately before v5, while keeping the functional crash guards.
    print("\nRestoring pre-v5 UI...")
    runpy.run_path(str(here / "restore_phase7_ui_v4.py"), run_name="__main__")

    print("\nPHASE 7 FINAL INSTALL: PASS")
    print("NEXT: run campaign_supabase_phase7_hotfix_02.sql in Supabase SQL Editor.")
    print("If not already installed, also run campaign_supabase_phase7_live.sql.")
    print("Then restart with: python frontend_2_8.py")


if __name__ == "__main__":
    main()
