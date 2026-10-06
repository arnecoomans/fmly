# Management commands

FMLY3's own commands, besides Django's. All are safe to run more than once.

## Setting up and releasing

**`prepare_release`** (`core`) - what a fresh database needs besides data: the tag *Loose end*, and the groups **Visitors** (may comment) and **Editors** (may add and change the archive). Accounts without a group join Visitors.

```sh
manage.py prepare_release                 # accounts without a group: Visitors
manage.py prepare_release --all-editors   # every active account: Visitors and Editors
```

The groups' permissions are set to what the command lists, so changes made to them in the admin are undone by a rerun.

**`create_default_pages`** (`core`) - the pages the site links to, in each language written (the cookie statement). Only creates what's missing; `--force` overwrites with the default text.

## Content

**`content_checksums`** (`content`) - fills in what files don't have yet: the SHA-256 checksum (an upload of a file that's already there is recognised by it) and an image's width and height. Reports files stored more than once. `--all` recomputes everything.

## The legacy import

**`import_all`** (`legacy_import`) - the whole import in order, then the release setup; see [The legacy import](legacy-import.md). The single steps are `import_users`, `import_places`, `import_persons`, `import_person_relations`, `import_content_tags`, `import_events`, `import_content` and `import_notes`.

- `import_content --files-only` - only attach files now found in `import/documents/`.
- `import_persons --no-dateless-deaths` - people without the "died, details unknown" events (for before the events are imported).

## After every update

`.post_update.sh` in the project root runs `create_default_pages`, `content_checksums` and `check` after each `update.sh` - see [Deploying](deploying.md).

## Checks

`manage.py check` includes FMLY3's own:

- `content.W001` - no tesseract program (OCR off)
- `content.W002` - no pytesseract
- `content.W003` - OCR language data missing

and cmnsd's checks of the API registrations (searchable fields must be stored text fields).
