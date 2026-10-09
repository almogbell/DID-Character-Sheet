# DID Mobile Sync

The Android application is a companion to the Windows DID Character Sheet. The Windows application remains the authoritative owner of character state, game-rule validation, persistence, and recovery.

Normal Android use does **not** load or edit a copied `.didchar` file. Instead, Android pairs with a running Windows DID Character Sheet and receives live character state from it.

## Version 1 goals

- Pair a phone with the Windows app using a short-lived pairing token / QR code.
- Reconnect to a previously paired computer without pairing again.
- Send the complete current character state to Android after connection.
- Keep HP, Adversity Tokens, and Improvement Points synchronized in both directions.
- Broadcast desktop-side changes immediately to Android.
- Reject unauthenticated clients and incompatible sync protocol versions.
- Clearly show disconnection rather than allowing divergent offline edits.

## Authority model

Android sends **commands**, not replacement character files. Windows validates each command using the real desktop character engine, performs the change, saves it through the normal desktop save path, then broadcasts the new canonical state.

This is deliberate: Android should not become a second independent implementation of DID rules.

See `protocol-v1.md` for the message contract.
