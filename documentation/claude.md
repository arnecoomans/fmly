# FMLY — Claude Documentation

## Project Overview

**fmly** (CMNS FMLY) is a family archive / annotated photo dump built with Django.
It lives at `fmly.cmns.nl` and is a personal project for the Coomans and Bake families.

**Purpose:** Organize, annotate, and share historic family documents — photos, news clippings,
and other memorabilia — with family members, with access control per user group.

**Path:** `/Users/Cooma001/Documents/Code/python/fmly.cmns.nl/`

---

## Tech Stack

- **Framework:** Django 5.2, Python 3.14, SQLite
- **Django config module:** `family` (`ROOT_URLCONF = 'family.urls'`)
- **Settings file:** `family/settings.py`
- **Image processing:** Pillow, pillow-heif (HEIC support)
- **PDF support:** PyMuPDF
- **Markdown:** python-Markdown (descriptions, notes, bios)
- **Family tree:** Graphviz
- **Secure file serving:** django-sendfile2 (nginx backend)
- **i18n:** EN + NL (`locale/`)

---

## Apps

| App | Purpose |
|-----|---------|
| `archive` | Core app — images, people, notes, comments, tags, attachments, locations |
| `cmnsd` | Shared utility layer — BaseModel, AJAX dispatch, FilterMixin, template tags |
| `datepicker` | (Disabled) Date-picker scheduling tool |

URL routing: `archive.urls` at `/`, `cmnsd.urls` at `/ajax/`, Django auth at `/`.

---

## Key Settings

| Setting | Value |
|---------|-------|
| `WEBSITE_TITLE` | `"Coomans' Family Archive"` |
| `FAMILIES` | `['Coomans', 'Bake']` — family collections used throughout |
| `PAGINATE` | `24` |
| `MEDIA_URL` | `documents/` |
| `MEDIA_ROOT` | `public/documents/` |
| `STATIC_ROOT` | `public/static/` |
| `STATICFILES_DIRS` | `project_static/` |
| `MASTER_CSS` | `fmly.css` |
| `NEW_USER_DEFAULT_GROUP` | `'familie - kijken'` |
| `MIN_COMMENT_LENGTH` | `4` |
| `DEFAULT_MODEL_STATUS` | `'p'` (published) |
| `DEFAULT_MODEL_VISIBILITY` | `'p'` (public) |
| `SENDFILE_BACKEND` | `django_sendfile.backends.nginx` |
| `LOGIN_REDIRECT_URL` | `archive:home` |
| `LOGOUT_REDIRECT_URL` | `archive:home` |

---

## Data Model

### BaseModel (cmnsd)
All archive models inherit from `BaseModel`:
- `token` — unique 10-char public ID (auto-generated, URL-safe)
- `status` — `'c'`=concept, `'p'`=published, `'r'`=revoked, `'x'`=deleted
- `date_created`, `date_modified` — auto timestamps
- `user` — ForeignKey to User (nullable, SET_NULL)

`VisibilityModel` adds:
- `visibility` — `'p'`=public, `'c'`=community, `'f'`=family, `'q'`=private

### Image (`archive/models/image.py`)
Core model. Key fields:
- `slug` — unique, auto-generated from title
- `source` — uploaded image file
- `thumbnail` — cached thumbnail path
- `title`, `description` (Markdown), `document_source`
- `year`, `month`, `day` — flexible partial dating
- `people` — M2M to Person
- `tag` — M2M to Tag
- `attachments` — M2M to Attachment
- `in_group` — M2M to Group (for grouping related images)
- `is_portrait_of` — OneToOne to Person
- `portrait_of` — M2M to Person
- `family` — CharField fallback when no family member can be tagged
- `visibility_frontpage`, `visibility_person_page` — Boolean display toggles
- `@ajax_function`: `origin`, `metadata`, `classification`, `actionlist`, `families`, `family_collection`
- `@searchable_function`: `familycollection`, `decade`

**Family collection** logic: derived from `people` last names / married names matching `settings.FAMILIES`,
with `image.family` as a manual override.

### Person (`archive/models/person.py`)
- `first_names`, `given_name`, `last_name`, `married_name`, `nickname`
- `gender` — `'m'`/`'f'`/`'x'`
- `slug` — auto-generated from `__str__()` on save
- `bio` (Markdown), `email` (private), `private` (BooleanField)
- `related_user` — links a Person to a Django User account
- Portrait crop fields: `portrait_x`, `portrait_y`, `portrait_w`, `portrait_h`
- Birth/death data via `Event` model (not direct fields)
- `@ajax_function`: `names`, `dates`, `parents`, `family`, `all_family`, `all_last_names`, `timeline`
- `@searchable_function`: `century`, `decade`, `last_names`, `familycollection`, `all_family`

### FamilyRelations (`archive/models/person.py`)
Stores two types of explicit relations:
- `('parent', ...)` — `up` is parent of `down`
- `('partner', ...)` — bidirectional

Siblings and inferred partners (shared child) are calculated dynamically via `get_family()`.
`unique_together = ('up', 'down', 'type')`.

### Event (`archive/models/Event.py`)
Linked to Person, Image, and Location via M2M.
Types: `birth`, `death`, `marriage`, `general`, `other`.
Fields: `year`, `month`, `day` (all optional), `title`, `description`.
Birth/death dates for a Person are fetched via `person.birth()` / `person.death()` — returns the related `Event`.

### Other Models
- `Tag` — labels for images and people
- `Category` — hierarchical image categories (FK to self)
- `Group` — groups of related images (M2M tags)
- `Attachment` — files linked to images (served via sendfile)
- `Note` — standalone markdown notes
- `Comment` — comments on images
- `Location` — geographic locations linked to events
- `Preference` — per-user preferences

---

## Views Inventory (`archive/views/`)

### Image Views
- `ImageListView` — home, filtered by decade/tag/uploader
- `ImageView` — image detail (`object/<slug>/`)
- `ImageRedirectView` — redirect by pk
- `AddImageView` — upload new image
- `EditImageView` — edit image metadata
- `RegenerateThumbnailView` — regenerate cached thumbnail

### Person Views
- `PersonListView` — list all people
- `PersonView` — person detail (`person/<pk>/<name>/`)
- `PersonRedirectView` — redirect by pk
- `AddPersonView`, `AddPerson` — two add-person paths
- `EditPersonView` — edit person
- `PersonAddRelationView`, `PersonRemoveRelationView` — manage family relations
- `SuggestFamilyView` — suggest family matches
- `TreeView` — family tree via Graphviz

### Other Views
- `TagListView`, `AddTagView`, `EditTagView`
- `NotesListView`, `NoteView`, `AddNoteView`, `EditNoteView`
- `CommentListView`, `aListComments`
- `AttachmentListView`, `AttachmentAddView`, `AttachmentStreamView`, `AttachmentDeleteView`, `AttachmentEditView`, `CreateImageFromAttachmentView`
- `LocationListView`
- `PreferencesView`, `SignUpView`

---

## CMNSD Module

Shared utility layer used by both `fmly` and the sibling `cmpng` project.

Key components:
- `BaseModel` / `VisibilityModel` — abstract base models (see above)
- `@ajax_function` / `@searchable_function` decorators (`cmnsd_basemethod.py`)
- `FilterMixin` (`cmnsd_filter.py`) — URL-driven queryset filtering
- AJAX dispatch system (`ajax_dispatch.py`, `ajax__crud_*.py`) — CRUD via JSON
- Template tags: `markdown`, `query_filters`, `queryset_filters`, `text_filters`, `math_filters`, `humanize_date`, `cmnsd`
- `cmnsd.urls` mounted at `/ajax/` for AJAX endpoints

### AJAX Pattern
`@ajax_function` methods on models expose structured data for the AJAX frontend.
The dispatch system routes `GET /ajax/<model>/<pk>:<slug>/` to the appropriate method.
Settings controlling AJAX: `AJAX_BLOCKED_MODELS`, `AJAX_PROTECTED_FIELDS`, `AJAX_RESTRICTED_FIELDS`,
`AJAX_ALLOW_FK_CREATION_MODELS`, `AJAX_ALLOW_RELATED_CREATION_MODELS`, `AJAX_MAX_DEPTH_RECURSION`.

---

## File / Media Layout

```
public/
  static/       ← STATIC_ROOT (collectstatic output)
  documents/    ← MEDIA_ROOT (uploaded files)
    files/      ← SENDFILE_ROOT (attachments, served via nginx)
    thumbnails/ ← auto-created thumbnail cache
project_static/ ← source static files (CSS, JS)
templates/      ← global templates
locale/         ← i18n translations (EN, NL)
```

---

## Code Conventions

- **4-space indentation** in most files (note: differs from cmpng which uses 2-space)
- Google-style docstrings where present
- Cached instance attributes via `hasattr(self, '_attr')` pattern throughout models
- Slugs auto-generated on `save()` for Image and Person
- `person.birth()` / `person.death()` return `Event` objects, not dates — access `.year`, `.month`, `.day` on the result

---

## User Rights System

- Access controlled via Django Groups
- Default new-user group: `'familie - kijken'` (read-only)
- At least two groups recommended: read-only and write-access
- `Person.private = True` limits information shared about that person
- `OBJECT_FORM_FIELDS` setting controls which relation fields appear in image forms:
  `['tag', 'in_group', 'attachments', 'is_portrait_of']`

---

## People Ordering

- `PEOPLE_ORDERBY_OPTIONS = ['last_name', 'first_name', 'year_of_birth']`
- `PEOPLE_ORDERBY_DEFAULT = 'last_name'`

---

## Common Gotchas

- `Person.birth()` / `Person.death()` query the database — cache results when looping
- Family collection is derived from `settings.FAMILIES` — add families there, not in the DB
- `Image.get_thumbnail()` only supports `.jpg`, `.jpeg`, `.png` — other formats return a placeholder
- Attachment files are served via nginx sendfile — direct media URL access is blocked in production
- Django auth URLs included at root (`''`) — standard paths like `/login/` work out of the box
- `datepicker` app is installed but commented out in `INSTALLED_APPS`
- `SITE_NAME` in settings still reads `'Vakantieplanner DEVELOPMENT'` — leftover from cmpng, not used by fmly templates
