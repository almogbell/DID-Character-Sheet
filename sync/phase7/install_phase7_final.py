from __future__ import annotations

import runpy
from pathlib import Path


def main():
    here = Path(__file__).resolve().parent

    print("Phase 7 base install...")
    runpy.run_path(str(here / "install_phase7.py"), run_name="__main__")

    print("\nPhase 7 UI repair v2...")
    runpy.run_path(str(here / "repair_phase7_ui_v2.py"), run_name="__main__")

    print("\nPHASE 7 FINAL INSTALL: PASS")
    print("Restart with: python frontend_2_8.py")


if __name__ == "__main__":
    main()
