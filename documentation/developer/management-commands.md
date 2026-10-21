# Management commands

FMLY3's own commands, besides Django's. All are safe to run more than once.

## Setting up and releasing

**`prepare_release`** (`core`) - what a fresh database needs: the tag *Loose end*, and the groups **Visitors** (may comment) and **Editors** (may add and change the archive). Accounts without a group join Visitors.

```sh
manage.py prepare_release                 # accounts without a group: Visitors
manage.py prepare_release --all-editors   # every active account: Visitors and Editors
```

The groups' permissions are set to what the command lists, so changes made to them in the admin are undone by a rerun.

**`create_default_pages`** (`core`) - the pages the site links to, in each language written (the cookie statement). Only creates what's missing; `--force` overwrites with the default text.

## Content

**`content_checksums`** (`content`) - fills in what files don't have yet: the SHA-256 checksum (an upload of a file that's already there is recognised by it) and an image's width and height. Reports files stored more than once. `--all` recomputes everything.

## People

**`gedcom_export`** (`people`) - one person as GEDCOM 5.5.1, to the console (`people/gedcom.py`, issue #463). `--depth N` adds their partners and children, N levels down: 1 is their family group, 2 adds the children's partners and the grandchildren.

```
manage.py gedcom_export aa7d8ab2bc064d65ad5b --depth=2 > coomans.ged
```

Living people - no death event - with initials only, no dates or notes; private people and outsiders left out, as is anything not published. Births and deaths, marriages on the families, partial dates as `ABT`/`BEF`/`AFT`, places with their parents, a biography as a note (mentions and links as text). Record ids from tokens, the same in every export.

## After every update

`.post_update.sh` in the project root runs `create_default_pages`, `content_checksums` and `check` after each `update.sh` - see [Deploying](deploying.md).

## Checks

`manage.py check` includes FMLY3's own:

- `content.W001` - no tesseract program (OCR off)
- `content.W002` - no pytesseract
- `content.W003` - OCR language data missing

and cmnsd's checks of the API registrations (searchable fields must be stored text fields).
