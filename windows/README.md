# DID Character Sheet — Windows

This folder documents the Windows desktop application.

The Windows app is the authoritative implementation of DID character rules, character storage, Improvements, Inventory, Notes, dice behavior, and mobile-companion synchronization.

## Releases

Windows releases use tags such as:

`v1.0.10`

The Windows updater reads:

`updates/windows.json`

The desktop and Android apps have independent version numbers and may be released separately.

## Mobile companion

The Windows application will host the authoritative character state for the Android companion. The phone should connect to the running desktop app rather than work from a copied `.didchar` file.
