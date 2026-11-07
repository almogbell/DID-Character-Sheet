# Problem 15 follow-up — secure compliant-character admission

This patch fixes the mismatch between Problem 12's automatic joining and Problem 15's hardened database permissions.

## Install (Windows)

Extract this ZIP into the **current** Windows project containing `frontend_2_8.py`:

- `campaign_cloud.py` (changed): uses `/rpc/did_admit_compliant_character` instead of direct writes to `/campaign_characters`.
- `campaign_admission.py` (changed): sends minimal character creation-rule details for server-side checks.
- `DID_Important_Tests/test_problem16_guarded_admission.py` (new): local regression tests.
- `PROBLEM_15_16_SERVER_ADMISSION.sql`: reference copy of the already deployed migration.

The SQL migration was **already applied** to Supabase DID-Suggestions by ChatGPT. Do not run it again in the same project.

Run from the Windows source folder:

`python -m unittest discover -s DID_Important_Tests -p test_problem16_guarded_admission.py -v`

This does NOT modify the Campaign Manager UI, Android sources, local .didchar files, or established shared-state protocol.

## Security and behavior

- Player must be authenticated and be a member of the selected campaign.
- The server compares creation metadata against its stored **current** campaign template.
- Existing pending or rejected exception requests prevent automatic admission.
- Previously admitted active characters retain their link through later rule changes.
- The database writes the initial cloud character state atomically with the link.
- Ordinary clients still have NO direct campaign-character INSERT/UPDATE permission.
- Existing DM exception request/decision RPCs remain in place.

**Limitation:** Character `.didchar` files live on untrusted client devices. Submitted metadata is checked by the server but can be falsified by a malicious client. Full anti-cheat enforcement would require server-authoritative character state and mutations or mandatory DM approval of every character.

The live two-account joining and approval checks are deferred to the final integration test.
