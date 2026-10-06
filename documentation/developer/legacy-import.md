# The legacy import

FMLY3 replaces an older FMLY site. Its data comes over with the commands in `legacy_import/`, from an export in `import/` - which is never committed: it holds family documents, personal data and password hashes.

```
import/
├── fixtures/     dumpdata JSON of the old site: auth_user.json, archive_person.json, ...
└── documents/    the old site's files
```

## Running it

```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py import_all
```

`import_all` runs the steps in dependency order, then the setup a fresh database needs:

| Step | Brings in |
|---|---|
| `import_users` | Accounts (without the old groups and permissions) |
| `import_places` | Places, their parents and alternatives |
| `import_persons --no-dateless-deaths` | People |
| `import_person_relations` | Parents and partners |
| `import_content_tags` | Tags and old categories (at pk + 1000) |
| `import_events` | Events; old kind *general* becomes *historical* |
| `import_persons` | Again: now the dateless deaths, where no death event exists |
| `import_content` | Images, attachments and books, their files, portraits, groups and comments |
| `import_notes` | Notes, with old-site links rewritten to the new pages |
| `content_checksums` | Checksums and dimensions of the files |
| `prepare_release --all-editors` | The Loose end tag; the groups; every account in Visitors and Editors |
| `create_default_pages` | The cookie statement |

`--skip-after` runs only the import steps.

## Principles

- **Old ids are kept** where possible, so a rerun finds each record again and updates it: no duplicates. Sources that share a model get fixed offsets (`legacy_import/pk_offsets.py`).
- **Nothing an import creates may take an old id** before that id is imported: such rows are made after the legacy rows (the dateless deaths, the *Collection* tag).
- **Id sequences follow the imported ids.** PostgreSQL doesn't move a sequence past an id inserted explicitly, so every import command ends with `reset_sequences()` (`legacy_import/sequences.py`) - otherwise the next new row, on the site too, collides with an imported one. On SQLite it does nothing.
- **Decisions live in the importer**, not in data migrations: renamed tags (`legacy_import/tag_layout.py`), kind mappings, links rewritten to new addresses (`legacy_import/links.py`).

## Re-running

A full rerun overwrites every imported record with the old site's values - edits made on the new site to imported records are lost. Two safe partial runs:

- **New files only:** files added to `import/documents/` later are attached to their records without changing anything else:

  ```sh
  .venv/bin/python manage.py import_content --files-only
  ```

- **One step:** any single `import_*` command can be run on its own; it's idempotent.

For a clean start: delete the database and `private/content/` and `private/cache/`, migrate, and run `import_all`.
