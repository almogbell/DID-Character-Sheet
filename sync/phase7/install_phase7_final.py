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
    # Earlier installers expected the original single Campaign menu block and
    # failed once Campaign Manager / My Campaigns had already been added.
    print("\nPhase 7 installer idempotency preflight...")
    runpy.run_path(
        str(here / "repair_phase7_installer_idempotency.py"),
        run_name="__main__",
    )

    print("\nPhase 7 base install...")
    runpy.run_path(str(here / "install_phase7.py"), run_name="__main__")

    print("\nPhase 7 UI repair v2...")
    runpy.run_path(str(here / "repair_phase7_ui_v2.py"), run_name="__main__")

    print("\nPhase 7 UI repair v3...")
    runpy.run_path(str(here / "repair_phase7_ui_v3.py"), run_name="__main__")

    print("\nPhase 7 UI repair v4...")
    runpy.run_path(str(here / "repair_phase7_ui_v4.py"), run_name="__main__")

    print("\nPhase 7 UI repair v5...")
    runpy.run_path(str(here / "repair_phase7_ui_v5.py"), run_name="__main__")

    print("\nPHASE 7 FINAL INSTALL: PASS")
    print("Restart with: python frontend_2_8.py")


if __name__ == "__main__":
    main()
