# Changelog

## [Unreleased]

## [26.04.2] - planned

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

### Query optimization — Person detail view (200 → 27 queries)
- `PersonView.get_queryset()` uses `Image.objects.optimized()` — eliminates N+1 per image for category, people, tags, groups
- `PersonView` applies `with_counts()` after storing `_clean_count` and overrides `get_paginator()` — same paginator fix as image list view
- `Person.get_family()` now returns a plain Python list (evaluated once); `get_parents()`, `get_children()`, `get_partners()`, `get_siblings()` filter the list in Python — eliminates 3+ repeated family SQL queries per page load
- Nested `Prefetch('events', queryset=Event.objects.filter(type__in=['birth', 'death']))` added inside the people prefetch — batches birth/death lookups for all tagged persons in one query
- `Person.objects.optimized()` no longer calls `with_images()` — images are fetched by the ListView queryset, not the person object

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

## [26.04.1] - planned
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
