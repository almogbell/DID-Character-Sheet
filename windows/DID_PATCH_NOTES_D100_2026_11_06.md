# DID Character Sheet 1.0.14 — Notes color + d100 mixed-roll patch

## Changed in this patch

- New **player-created** notes receive a random saved HEX color, with colorful hues and saturation that avoid gray, black, white and muddy brown. A recently used hue is avoided when possible.
- Existing notes, preset palette entries, and managed notes (Animal Buddy, system notes, etc.) are left intact.
- Light and dark themes display corresponding light/dark versions of the same saved HEX hue; the saved HEX value remains unchanged, including after manual color-wheel changes.
- The Notes page, redesigned note cards, and temporary reference-note popup use consistent theme-projected colors.
- The physical d100 and regular dice now have **separate, non-overlapping display regions** in mixed rolls. The result card uses the combined on-screen bounds.
- d100 and ordinary dice selected from **Roll Other Dice** use the same input HEX color and matching CSS canvas filter. Their different 3D lighting engines may still produce slightly different perceived highlights.
- d100 uses less GPU memory and approximately half as many mesh draw calls per die: 100 face meshes are combined into one, and label textures are smaller.
- d100 damping/sleep thresholds have been tuned to shorten the long settle time without inventing die results. Physical orientation still determines the face value.
- If a physics roll fails, an explicit message is displayed rather than silently producing no result.

## Patch installation

1. Fully close DID Character Sheet.
2. Extract the patch archive into the **existing source directory** containing `frontend_2_8.py` and `dice.html`, replacing files.
3. From PowerShell in that source directory, run `./.venv/Scripts/python.exe ./frontend_2_8.py`.
4. Do not apply the patch to a previously built installer or executable: these changes require a new build for packaged releases.

## Recommended checks

- Create 10+ personal notes; check varied pastel color without gray/black/white/brown.
- Switch Light → Dark → Light and confirm each note keeps its hue and manually selected colors persist across restart.
- Roll 1×d100, 2×d100, 1×d100 + 1×d8, and d100 + d6 + d20; confirm all appear side-by-side, totals/history appear, and none take an unusually long time.
- Confirm a normal multi-dice roll without d100 still appears correctly.

## Verification and limits

- Static tests, Node JS syntax checks, pure color calculations, and Cannon physics-only simulations pass.
- 8 simulated simultaneous two-d100 rolls settled within 5.4 seconds in this environment; animation timing on Windows depends on GPU performance.
- Full Chromium/Qt WebEngine integration could not be executed here; the test browser was blocked by local-page security. Please verify visually on Windows.
- Does not change character saves or cloud records directly; back up characters before upgrading as usual.
- No unrelated UnifiedReader files added.
