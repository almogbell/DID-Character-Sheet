# DID 1.0.14 — Dice Results / Qt WebChannel Fix

## User-reported error

```
js: Not allowed to load local resource: qrc:///qtwebchannel/qwebchannel.js
js: [DID Dice] Qt WebChannel unavailable; rolls cannot reach the character sheet.
```

The preceding dice patch moved the page to a restricted `http://127.0.0.1` origin so DiceBox modules and physics assets could load, but still referenced the Qt WebChannel JavaScript using the `qrc:///` URL. Qt WebEngine refused that cross-scheme resource load. As a result, the animation worked but the roll summary did not reach Python; the result popup and Previous Rolls did not update.

## Change

- `dice.html`: replaces the blocked `qrc:///qtwebchannel/qwebchannel.js` reference with `./qtwebchannel/qwebchannel.js`.
- `dice_asset_server.py`: reads the genuine `qwebchannel.js` bundled in the user's PySide6 `:/qtwebchannel/qwebchannel.js` resource and serves *only this script* on the dice page's loopback origin. Keeps the deny-by-default asset restrictions and does not serve private character files.
- `test_did_numeric_dice_regression.py`: tests the same-origin script, denies arbitrary Qt or project files, and verifies the actual Qt resource when PySide6 is available.

## Apply and run

1. Fully close DID Character Sheet.
2. Extract `DID_WebChannel_Result_Fix.zip` into the existing project folder containing `frontend_2_8.py`, choosing to replace files.
3. Run from that folder:

   ```powershell
   .\.venv\Scripts\python.exe .\frontend_2_8.py
   ```

4. Roll one ability die and one Roll Other Dice; check the little result card above the dice, Previous Rolls, and that the `qrc:///` warning is gone.
5. If necessary run `python -m unittest test_did_numeric_dice_regression -v` in the same Python environment.

## Verification and limitations

- Dice asset and security test suite: 6 tests passed; 2 GUI/Qt-resource checks skipped because PySide6 is unavailable in this Linux environment.
- Inline JS bootstrap and module scripts both passed `node --check`; Python source compiled.
- Actual QWebEngine integration and visual display must be verified on Windows with the installed PySide6 package.
- No changes to dice probability rules, characters, saves, campaign sync, or existing 3D dice animation.
