# DID Improvement Editor — agreed design and implementation notes

Target: existing DID 1.0.6 editor with online suggestions (the package previously supplied as `DID_1_0_6_ONLINE_SUGGESTIONS_SETUP.zip`). No character save file migration.

## Final agreed UX

- Two permanently separate descriptions: **Picker description** and **Character sheet description**. Never merge them automatically. Existing `owned_summary` continues to control sheet display; existing `description` controls picker display.
- Both descriptions are actual WYSIWYG editors: select text and use B, I, U, bulleted lists, numbered lists, or keyboard shortcuts Ctrl+B/Ctrl+I/Ctrl+U. Neither HTML tags nor double-asterisk formatting appear in editing fields. The supported storage markup is only simple bold/italic/underline, lists and line breaks; approved catalog content is authoritative.
- The *always visible* live preview is directly below each description, within the same section. These are rich text previews, not full screenshots of each character-sheet widget. Preview updates on text change. Changing the preview does not publish anything.
- Left: searchable improvement list; New prominent; Duplicate and Delete tucked into context menu.
- Right: simple Basic information, collapsed Rules & options, two large writing sections, Empowerments and Scaling sections below.
- Header: Save draft, Send suggestion, More. The More menu preserves Retry queue and Export; owner mode additionally exposes local review, authenticated online inbox, and import. Admin authorization must still be enforced by the Supabase database, not by button visibility.
- Choice IDs remain unchanged internally and are presented as readable names. Adding a choice uses an existing supported choice type. New backend choice types require backend work; creating arbitrary identifiers is intentionally not exposed.
- Editing a scaling level description opens the same visual editor, not a raw-markup table cell.
- Edits are drafts. They do not affect the live catalog until existing approval flow. Suggestions never automatically publish. Approved changes continue to require application restart as in the source implementation.
- Pending edits are saved when changing improvement, creating/duplicating/deleting, and when closing the editor dialog. Untouched descriptions retain their original serialized text byte for byte.

## Files included

`improvement_editor.py` is the only application source file that must be replaced. `suggestion_cloud.py` and its existing public configuration must remain in the application directory. Do not replace `catalog_editor_data`, saved characters, `character_API.py`, `improvements_ui.py`, or the current dice files.

## What this first implementation does *not* prove or implement

- No live PySide6 GUI verification was possible in this runtime; test keyboard shortcuts, visual resizing, list toggling, preview position, and closing the dialog on Windows before release.
- The preview is a rich-text preview, not a pixel-identical instantiation of the real Improvements card; some stylesheet and layout differences are possible.
- The existing review dialog still presents technical differences for some complex fields. A future review redesign can add a visual rich-text comparison; it is not silently claimed to be finished here.
- The existing online suggestion service still needs your Supabase configuration and independently verified row-level-security rules. This patch does not deploy the cloud backend.
- The legacy advanced mechanics, arbitrary new choice types, and empowerment hierarchy are preserved rather than redesigned wholesale.

## Windows installation

1. Back up the entire `current code` directory and the `catalog_editor_data` folder.
2. Extract this ZIP; copy `improvement_editor.py` into your latest DID 1.0.6 `current code` directory, replacing that file only.
3. Keep `suggestion_cloud.py` from the previous online-suggestions package alongside it. Keep `suggestions_config.json` if you already configured it.
4. Run DID from Python and open Tools → Improvement Editor. Test both descriptions, their previews, keyboard shortcuts, switching entries with unsaved text, New/Duplicate/Delete, and a local suggestion before building an EXE.
5. If successful, rebuild PyInstaller and your existing Inno Setup installer. Increment app and installer versions only when you decide to release.

Rollback: restore your backed-up `improvement_editor.py`. Drafts and character files have not been modified by copying this patch; back up your draft catalog before using the editor with actual data.
