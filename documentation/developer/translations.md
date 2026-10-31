# Translations

FMLY3 is written in English and translated into Dutch (`LANGUAGES` in `fmly/settings.py`). Each user picks a language in their preferences; without one, the browser's.

## Where the strings live

| Strings from | Translated in | Why |
|---|---|---|
| FMLY3 (templates, models, forms, views) | `locale/nl/LC_MESSAGES/django.po` | the project's own |
| cmnsd (edit mode, the API's messages, accounts, error pages) | `cmnsd/locale/nl/LC_MESSAGES/django.po` | inside cmnsd, so every project on it - cmpng too - gets the same Dutch. Django finds an app's own `locale/` by itself |

Both are committed with their compiled `django.mo`: the server doesn't need gettext's tools, and an update brings the translations along.

## The words

- **je**, not u - a family archive, among relatives.
- An item (photo, document, book, object) is a **stuk**, items are **stukken**.
- Visibility: **Openbaar · Leden · Familie · Privé** - *community* is **leden**: everyone with an account.
- Roles: onderwerp, maker, geadresseerde, afgebeeld, mogelijk afgebeeld, eigenaar.
- Kinship as in Dutch genealogy: overgrootvader, betovergrootvader, oudovergrootvader; achterkleinkind.
- Loose ends are **losse eindjes**, housekeeping is **onderhoud**, edit mode is **bewerkmodus**; *fine as it is* is **prima zo**.

## After changing or adding strings

```
# FMLY3's strings (not cmnsd's, not the virtual environment or the import data)
.venv/bin/python manage.py makemessages -l nl --ignore='cmnsd/*' --ignore='.venv/*' --ignore='import/*' --ignore='fixtures/*'
# cmnsd's strings, from inside cmnsd
cd cmnsd && ../.venv/bin/django-admin makemessages -l nl --settings=fmly.settings --pythonpath=.. && cd ..
```

New strings arrive with an empty `msgstr`, changed ones marked `#, fuzzy` (with the old translation as a guess) - translate those, remove the `fuzzy` mark, then:

```
.venv/bin/python manage.py compilemessages -l nl --ignore='.venv/*'
```

and commit the `.po` and `.mo` - cmnsd's in cmnsd, first. A string with a placeholder keeps it exactly: `%(name)s`, `%(counter)s`, `{label}`.

## Writing strings that translate well

- **Whole sentences**, not glued pieces: the word order differs in Dutch.
- **No plurals built by adding an "s"** (`%(kind)ss`) - use `ngettext` / `{% blocktranslate count %}`.
- **Context for short words** that mean different things (`pgettext('relation', 'son')`).
- **Tests run in English**; switch with `translation.override()`, never `activate()` ([Testing](testing.md)).
