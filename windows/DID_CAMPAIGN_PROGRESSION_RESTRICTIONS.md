# DID 1.0.14 — Campaign progression restrictions

**Campaign-linked or in-progress campaign characters:** the Tools menu no longer offers Level Up, Adjust Resources, or Improvement Editor. Double-clicking the IP count does not grant points. The four underlying action handlers independently return without modifying the character.

**Standalone characters:** these controls remain available, including standalone characters created using a standalone template with creation rules.

The campaign status is determined without network requests from the existing AppData campaign link record, or the active character-specific pending campaign marker. No campaign or saved-character data is modified by this patch. This is a desktop UI restriction, not an authorization rule on data imported through other tools.

Test: `python -m unittest -v test_did_campaign_progression_policy.py`

Limitation: a campaign draft that has never linked successfully and whose in-memory pending marker is lost on restarting the app is not always distinguishable from a standalone template character; the restriction reliably applies to approved/pending characters represented in the local campaign-links store.
