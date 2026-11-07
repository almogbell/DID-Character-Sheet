# DID Character Sheet 1.0.14 — Mobile Companion scrolling fix

## Symptom
The Mobile Companion window showed a vertical scrollbar alongside its QR and paired-phones columns at the normal desktop size. Scrolling could push the column headings out of view even when no paired phones were listed.

## Changes
- Increased the default Mobile Companion window height from 530 to 570 logical pixels (clamped to the available screen).
- Added adaptive QR-panel sizing in the side-by-side layout: it uses the full 212-pixel QR image when space allows and shrinks only as much as needed on shorter windows.
- Preserved the original QR pixmap, so window resizing re-renders the display without reducing QR quality through repeated downscaling.
- Refit the QR when the viewport changes height (including pairing instructions and status wrapping), so the unnecessary scrollbar disappears at normal window sizes.
- Kept the paired-phones list's own scrollbar for long device lists and the middle scroll area as a fallback for genuinely narrow/short screens. Pairing buttons remain outside the scrollable area.
- No pairing protocol, device-management behavior, or saved character files changed.

## Validation
Python syntax passed. Eight previous layout-contract checks and seven new layout fit/behavior tests passed. The real PySide6 GUI layout must still be inspected on the user's Windows desktop; PySide6 is unavailable in the test container.

## Apply on Windows
Close the application, then extract `DID_Mobile_Companion_Scroll_Patch.zip` directly into your existing source project folder, overwriting matching files, before launching `frontend_2_8.py` again.

## Retest
1. Open Mobile Companion at its default size: no outer scrollbar; the network and Paired phones headings are visible.
2. Start pairing: QR, instructions, expiration text, list, and bottom buttons remain visible together.
3. Resize the dialog smaller: the QR adapts rather than immediately showing a scrollbar.
4. Narrow the dialog below 690 px: stacked layout still scrolls when genuinely necessary.
5. Pair, rename, and remove a phone; QR scanning and button actions still work.
