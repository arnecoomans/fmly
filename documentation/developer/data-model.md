# Data model

The archive's objects and how they relate. Field-level detail is in the models themselves; this is the map.

## People

**`Person`** (`people/models/Person.py`)
- Names: `given_name` (all official first names), `called_name`, `last_name` (at birth), `married_name`, `nickname`.
- `gender`, `biography` (Markdown), `family_connection` - *family*, *possibly family* or *outsider* (the people list's filter).
- `private` - see [Visibility and access](visibility-and-access.md); `related_user` - the account this person is.
- Status and visibility, an owner, a token and a slug: `/person/<token>/<slug>/`.

**`PersonRelation`** (`people/models/PersonRelations.py`) - `person_from` → `person_to` with a `relation_type`: *parent* (from parent to child), *partner*, or *other*. Siblings aren't stored - they're computed from shared parents, half-siblings included. The rules for adding relatives are in `people/relatives.py`.

Birth and death are **events**, not fields: `person.birth` and `person.death` find them.

## Content

**`Content`** (`content/models/Content.py`) - one uploaded file per row.
- `kind`: *photo*, *document*, *book*, *object*, *recording* or *unknown*; a detail row per kind holds what's specific (`PhotoContent.photo_kind`, `DocumentContent.document_kind` and language, `BookContent` author and publisher - a book's date is when it was published, it has no year of its own).
- `name`, `description`, `source`, a partial date (`PartialDateMixin`), `file` with `original_filename`, `checksum` (SHA-256), `width` and `height` as shown, and its own thumbnail crop (`thumb_crop_*`, `thumb_rotation`).
- Links: `people`, `tags`, `places`, `events`.
- **Parts:** `parent` and `position` - the pages of a book or a letter. One level deep: a part has no parts. Position 0 marks a variant of the whole (a colorized version).

**`Transcript`** - the text of an item: *original* or *translation*, a language, a method (*manual*, *automatic*, *automatic, checked*) and `incomplete`.

**`Portrait`** - a photo as someone's portrait (person × content), with a crop and rotation per person; one is primary.

## Events and places

**`Event`** (`events/models.py`) - `kind`: *birth*, *death*, *marriage*, *migration*, *historical* or *other* (with `kind_freetext`); an optional `title`, a partial date, `people`, `places`, and the content that documents it.

**`Place`** (`places/models.py`) - `name`, `alias`, a `parent` place (`HierarchyMixin`: *Batavia* within *Java*), alternatives for the same place under another name.

## Research and conversation

**`Note`** (`notes/models.py`) - `kind`: *to do*, *question*, *hypothesis*, *conclusion*, *context* or *scratch*; `title`, `body` (Markdown), a partial date, links to people, content, places, events, tags and other notes.

**`Comment`** (`core/models.py`) - on any object (a generic foreign key), with its own visibility.

**`Tag`** (`core/models.py`) - hierarchical (`HierarchyMixin`): *Collection: Krangan 81*. The tag **Loose end** marks something for later.

## Accounts and site

- **`Preferences`** (`core/models.py`) - per account: `language`, `family` (the accounts counted as family), `ui_state` (remembered folds and sorts).
- **`LooseEndDismissal`** (`dashboard/models.py`) - "fine as it is" for one item in one loose end (generic foreign key).
- **`Page`** (cmnsd) - the site's pages, one row per language.

## Dates

Most objects use `PartialDateMixin`: `year`, `month`, `day` - each optional - and `date_qualifier`: *exact*, *ca.*, *before* or *after*. Never fill in a guessed part; show a date with the `partial_date` filter.
