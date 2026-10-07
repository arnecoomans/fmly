# Changelog

## [26.10] - FMLY 3.0 (unreleased)

A ground-up rebuild: a new content design, centred on content and people instead of on separate records. FMLY 3.0 shares no code with FMLY 2 and starts from a new database, filled from the old one by the legacy import. What it does: [README.md](README.md); how to use it: [documentation/usage/](documentation/usage/readme.md).

### New
- **Dashboard** - on this day and the calendar, recently added, from the archive, the latest comments, an inbox for uploads, loose ends to complete, and your own place in the archive
- **People** - names, birth and death with partial dates (ca., before, after), parents, partners and children edited on the person's page, a life timeline with ages
- **Photos & documents** - one kind of content for photos, documents, books, objects and recordings, with their parts; who is on a photo, dates and places, transcripts with OCR
- **Events and places** as pages of their own, linking people and content
- **Research** - notes with questions, leads and conclusions; one search across everything, including transcripts and biographies; comments
- **Edit mode** - change things on the page itself; every change in the admin history
- **Privacy** - community-visible by default, family-visible and private where needed, drafts until published; no external services, everything loaded from the site itself

### Under the hood
- Built on **cmnsd 3** (git submodule, branch `fmly`): models with status and visibility, an API, edit mode and cmnsd.js - see `cmnsd/documentation/`
- Django 6, Python 3.14; files served through Django's access checks (sendfile with nginx); static files with hashed names
- Settings from `.env` - template: `.env.example`
- Apps: core, people, content, events, places, notes, dashboard - replacing the single `archive` app; the project package is now `fmly` (was `family`)

### Moving from FMLY 2
- New database, filled once from the FMLY 2 export by a legacy import; partners FMLY 2 only implied (two parents of a child) and book authors as text were then made explicit through loose ends. The import and those loose ends are removed again ([#457](https://github.com/arnecoomans/fmly/issues/457))
- Old person addresses (`/person/<slug>/`) redirect to the person's new page
- The last FMLY 2 version stays available as release 26.04.3

## [26.04.3] - final FMLY 2 release

- Birthday calendar: birthdays by month, with years of birth and death
- Books and collections: books with author, year, publisher, ISBN, cover, people and tags; collections ("Grandpa's shelf") with read status and notes per book
- Admin: "soft delete" and "restore" set the status (deleted / published) instead of the old `is_deleted` flag
- [Bugfix] Partners are now also found through a shared child, when no partner relation was recorded
- [Bugfix] Book pages redirected to a non-existing URL name after saving
- Update cmnsd and requirements

## [26.04.2]

### Query optimization — Image list view (~400 → 12 queries)
- Add `ImageQuerySet` and `ImageManager` to `archive/models/image.py` with `with_relations()`, `with_detail()`, `with_counts()`, `optimized()`, and `optimized_detail()` methods
- `with_relations()` uses `select_related` for category, category__parent, is_portrait_of and `prefetch_related` for people (with nested birth/death events), tags (with counts), in_group, loved_by
- `with_counts()` annotates comment_count, attachment_count, category_image_count, tag_count, group_count — eliminating per-row COUNT queries
- `ImageListView.get_paginator()` overridden to use `_clean_count` — prevents Django from wrapping the annotated queryset in a subquery for pagination COUNT
- `ImageListView.filter_objects()` uses the prefetch cache (`queryset.filter(visibility_frontpage=False).count()` remains, but main query is batched)
- Templates updated: `love.html` uses `|length` on prefetched `loved_by`; `attachments.html` uses `image.attachments.all` from cache; `in_group.html` uses `{% with %}` to avoid duplicate group image fetches

### Query optimization — Image detail view (29 → 20 queries)
- `ImageView.get_object()` now uses `Image.objects.optimized_detail()` instead of bare `get_object()` — enables prefetch batching for all related objects
- `in_group.html` refactored: `group.images.all` evaluated once per group via `{% with %}`, reused for count (`|length`) and iteration — removes 3 queries per group
- `actionlist.html` and `love.html` use `user.preference in image.loved_by.all` (prefetch cache) instead of `image in user.preference.favorites.all` (full favorites scan)

### Query optimization — Person detail view (200 → 31 queries)
- `PersonView.get_queryset()` uses `Image.objects.optimized()` — eliminates N+1 per image for category, people, tags, groups
- `PersonView` applies `with_counts()` after storing `_clean_count` and overrides `get_paginator()` — same paginator fix as image list view
- `Person.get_family()` now returns a plain Python list (evaluated once); `get_parents()`, `get_children()`, `get_partners()`, `get_siblings()` filter the list in Python — eliminates 3+ repeated family SQL queries per page load
- Nested `Prefetch('events', queryset=Event.objects.filter(type__in=['birth', 'death']))` added inside the people prefetch — batches birth/death lookups for all tagged persons in one query
- `Person.objects.optimized()` no longer calls `with_images()` — images are fetched by the ListView queryset, not the person object
- Family logic extracted to `archive/services/family_relations.py`; `_build_from_prefetch` uses already-prefetched `relation_down`/`relation_up` (zero extra queries for direct family); siblings fetched in one query with events pre-warmed via nested `Prefetch`; co-parents for children batched in one query and stored as `child.co_parents` — eliminates per-child `get_family()` DB fallback from template

### Query optimization — Person list view (1169 → 22 queries for 211 people)
- Add `PersonQuerySet.with_annotations()` — annotates `annotated_birth_year`, `annotated_death_year` (correlated subqueries) and `image_count`, `note_count` (COUNT annotations) on the queryset
- Add `PersonQuerySet.optimized_list()` and `PersonManager.optimized_list()` — used by `PersonListView` instead of `optimized()`
- `get_lifespan_data()` checks for `annotated_birth_year`/`annotated_death_year` first before falling back to the events prefetch — no migration or invalidation hooks required
- `person_link.html` updated to use `person.image_count`, `person.note_count`, and `person.get_lifespan_data` instead of per-person `.all.count` calls and `person.birth.year`/`person.death.year`

### Bugfix
- `person_family.html` used `.exists` and `.all` on `person.siblings`, `person.partners`, `person.children` — these now return Python lists after `get_family()` refactor; template updated to use list truthiness and direct iteration
- `without` template filter in `cmnsd/templatetags/queryset_filters.py` now handles list input in addition to querysets — required for children's co-parent display
- `Person.timeline()` used queryset union (`|`) on `get_parents()` and `get_children()` — now combines lists and passes ID lists to `Event.objects.filter(people__in=...)`

### Query optimization — Event model
- Add `EventQuerySet` and `EventManager` with `with_relations()` and `optimized()` — prefetches `people`, `locations`, `images`
- `Event.get_title()` replaced `.exists()` guards with truthiness checks on `.all()` — uses prefetch cache, avoids up to 4 queries per event
- `Event.image_count()` uses `len(self.images.all())` instead of `.count()` — uses prefetch cache
- `PersonQuerySet.with_events()` now also prefetches `events__people` — `get_title()` is cache-warm on person detail page

### Refactor
- `Group` and `Attachment` models extracted from `archive/models/image.py` to their own files (`group.py`, `attachment.py`); `__init__.py` updated
- Family relation logic extracted from `Person` model methods into `archive/services/family_relations.py`; model methods are now thin wrappers (`get_family`, `get_parents`, `get_children`, `get_partners`, `get_siblings`, `get_father`, `get_mother`)

## [26.04.1] - skipped
- [Bugfix] `Person.all_last_names()` and `all_places()` looped over all Person records in Python — replaced with `.values_list().distinct()` queries (2 queries each instead of N)
- [Bugfix] `Person.timeline()` fired one DB query per family member — replaced per-member loops with a single Event query using `Q` objects and subqueries
- [Bugfix] `get_safe_slug()` on Image fired a DB query on every loop iteration — now fetches conflicting slugs upfront in a single query and checks against a set
- Deleting a Person cascades and deletes their portrait Image - now it sets the remote relation as NULL. Migration required.
- Add Django Debug Toolbar when `DEBUG=True` — auto-enabled via conditional block in `settings.py` and `urls.py`
- Implement `.env` for secure hosting — `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DATABASE_URL` moved out of `settings.py` into environment variables via `django-environ`; `settings.py` is now safe to commit; `.env.example` added as template
- Update cmnsd module to reflect changes made for cmpng
  - Implement improved naming and functionality of BaseModels
  - Implement improved naming of Mixins
  - Use newer version of Bootstrap CSS and JS
  - Use updated version of cmnsd.js
- Update translations
- Update requirements

## [26.04] - 2026-04-04

Long standing release.
