# Changelog

## [26.10.1] (unreleased)

### New
- **Add pages to an item** - in edit mode under *Parts*: drop files, and each becomes the next part, in name order - taking over the whole's visibility, and for a document or book its kind; a loose item with the same file becomes the part ([#485](https://github.com/arnecoomans/fmly/issues/485))
- **Nederlands** - the whole site in Dutch (je, stuk, leden): the browser's language by default - also before signing in - or a choice in the preferences; FMLY3's strings and cmnsd's, which cmnsd now carries itself. Pages say which language they're in (`<html lang>`), for screen readers and browsers
- **Who is where on a photo** - a frame around each person whose place is known: their name on hover (or a tap), a question mark for possibly depicted, linked with their card; *the photo only* or *who is where* under the photo, remembered. In edit mode: point out, redraw, remove, and *use as portrait* for someone without one. The frames started from the portrait crops ([#480](https://github.com/arnecoomans/fmly/issues/480))
- **Comment visibility** - each comment shows who may read it; a new comment takes its item's visibility, may be narrower, never wider; changeable by its author or staff in edit mode. Changing an item's visibility changes no comment by itself: a notice offers to narrow the wider ones (or, made wider, to widen the narrower ones: your own, or as staff all of them), and the loose end *comments wider than their item* shows where an item was narrowed after them - on purpose, or by mistake ([#481](https://github.com/arnecoomans/fmly/issues/481))
- **A document's pages, gathered** - the whole's page shows the people and events of its pages: *on its pages*, *documented by its pages*, each with the page number
- **Make an event from an item** - under *Events* in edit mode: one dialog makes the event a dated item documents, on its date, its name as the title to rewrite, with its places and people to tick; who it replaces moves from the item to the event, who's on it or made it stays on both. On a page of a document, that page is the proof ([#487](https://github.com/arnecoomans/fmly/issues/487))
- **A tag's visibility and status** - on its page in edit mode, as for an item: who may see it, and publish a concept. A parent you may not see doesn't exist for you: its children read as tags of their own - in chips, the picker, search, the path on their page and /tags/; the parent's page says how many of its tags are wider
- **An event needs a year** - except a birth or a death: without one it had no place on any timeline and seemed lost. Not sure: a guess with *ca.*. Refused when adding, when removing the year, and when an undated birth becomes another kind
- **Birth and death when adding someone** - the new-person dialog (and /people/new/) has a *born* and a *died* row: date and place, or *died, details unknown*; each becomes their birth or death event, an empty row none. *Died* opens by itself when adding a parent - no more opening their page for the basics
- **Documentation from an event** - in edit mode under *documented by*: drop files, each a draft in your inbox linked as the event's proof - not to its people, date or places; a file already in the archive is linked instead
- **Artwork** - a new kind for what's made by hand - a painting, drawing, miniature, silhouette, engraving: a picture like a photo, with its kinds (*kind of picture*), so a painted portrait suggests *subject*, can be someone's portrait and counts among pictures without people (the loose end, renamed from *photos without people*); *object* is for things kept
- **Point out a portrait's sitter** - on a photo or an artwork, the *subject* can be pointed out too, so a portrait's sitter gets *point out* and *use as portrait*; on a document a subject still can't
- **A long note in sections** - in edit mode a note with headings has a pencil per section - a heading and what follows - and *+ section* at the end; the whole text stays one, its pencil at the bottom
- **Purge people, events, notes and comments** - housekeeping's *deleted items* lists every deleted kind, with what goes along: a person takes the events only they are in, never purged while linked to a user account; mentions of it are counted. Each links to what it's about - a person's family and namesakes, an event's people and places - and to the admin, to check why it was deleted (a double?) before it goes
- **Login links** - staff mail a family member a link that signs them in once (an invite, from the admin or *Accounts* - which now shows each account's email address and open link, and *approve and send* for a new one - with a message and a page to land on); the sign-in page offers *Mail me a login link*. Stored as a hash, revocable, only through a button (mail scanners), never for inactive accounts; to yourself too, to sign in on another device. Off unless `CMNSD_LOGIN_LINKS=True` in .env ([#492](https://github.com/arnecoomans/fmly/issues/492))
- **Date and places from the event** - an item documenting an event, without a date or places of its own: in edit mode, *from the event* copies the event's date (with how sure it is) or its places with one click - offered, never set by itself
- **A source cited counts** - an event without documentation whose description cites a source (a link, *Bron:*, *Uit:*) is done, its source outside the archive: listed apart under *source cited* on the loose end, a third part in its bar; a pill per kind to work through one kind at a time
- **Search by initials** - *P.W.A. Coomans*, *p. w. a.* or *pwa* finds Pieter Willem Anthonie Coomans, as documents name people; *Ch.* finds Christiaan. Also for an event's people and a book's authors; on the search page, people named by every word first
- **People linked twice** - Housekeeping lists people linked to a document that also documents their event: the event shows it on their page already, so the direct link can go where the document is evidence, not theirs. The rule - evidence to the event, what's theirs to the person - in the usage docs
- **Tag counts** - a tag counts the people and notes it holds too, not only items: *Loose end* on three people no longer says 0
- **Quiet transcripts on photos** - on a photo, an object or a recording the transcript shows once there is one; in edit mode a small *+ transcript*

### Under the hood
- [Bugfix] A parent made from a typed path ("Indozoektpost: 04" in a tag picker) started as a concept no one saw: it now starts as its child - published, as visible (cmnsd `HierarchyMixin`)
- cmnsd: `RegionMixin` (a box on an image as fractions), `regions.js` (linked regions, marking on an image), `gallery.js` (which item shows)
- Person rows: their visibility, portrait and pointed-out icons in one line under the name; the row's styles in `components.css` (also loaded on an item's page)
- Web hosting: a Memory section - swap, and the next steps if a large scan still runs the server out of memory

## [26.10] - 2026-10-21 - FMLY 3.0

A ground-up rebuild: a new content design, centred on content and people instead of on separate records. FMLY 3.0 shares no code with FMLY 2 and starts from a new database, filled from the old one by the legacy import. What it does: [README.md](README.md); how to use it: [documentation/usage/](documentation/usage/readme.md).

### New
- **Dashboard** - on this day and the coming week (births, marriages, deaths and history) and the calendar, recently added, from the archive, the latest comments, an inbox for uploads, loose ends to complete, and your own place in the archive; blocks fold, remembered per user
- **People** - names, birth and death with partial dates (ca., before, after), parents, partners and children edited on the person's page, a life timeline with ages
- **Transcripts as written, with a little Markdown** - headings, bold and italic, tables and mentions; nothing that changes a character (no lists or HTML; a footnote asterisk stays one); select words and *@ mention* to link who's named - the words stay as written, and the item shows under *mentioned in* ([#474](https://github.com/arnecoomans/fmly/issues/474))
- **One birth, one death** - a person has one of each, and each is one person's: refused on every way in, and Housekeeping lists what's from before
- **Same day** - on a timeline, the events page and a place, a row on the exact date of the one above says *same day*: twins, a double wedding
- **Proof you can see** - an event's page shows the items documenting it as thumbnails, and *choose a page* narrows a document with parts down to the page that proves it; on a timeline its proof folds out from a line of icons; a person's *Content* adds *related content*: items documenting their own events, not linked to them
- **Event rows read short** - a timeline, the dashboard, an item's or a place's page show an event's description up to its first blank line, with *read more* to the event's page
- **Roles of people on an item** - subject, creator, addressee, depicted, possibly depicted or owner - in that order of weight - chosen per person in edit mode and shown under their name; a person's *Content* filters by role. Existing links have no role yet: the loose end *people on items without a role*, with a bar, lists them - set there, or with one click to the role the item's kind suggests (a portrait: subject; a group photo: depicted) ([#471](https://github.com/arnecoomans/fmly/issues/471))
- **Event kinds: engagement, appointment, discharge** - an engagement names itself (as a marriage, without making partners); an appointment or discharge says which in its title. For GEDCOM: ENGA, OCCU, RETI
- **Mentions that lead nowhere** - housekeeping lists mentions of what's gone, revoked or deleted; *remove link* keeps the words. Revoking or deleting something that's mentioned warns first, a mentioned place doesn't count as unused, pickers and `@` no longer offer what's revoked or deleted, *revoked, to review* lists people, events and notes too, and mentioning something not every reader sees (family only, private, a draft) shows a pill while choosing and a warning on save
- **Mentioned in** - a person's, item's, event's, place's or note's page lists the biographies, descriptions, notes and comments that mention it - those you may read ([#470](https://github.com/arnecoomans/fmly/issues/470))
- **@ to mention** - in a biography, description, note or comment, `@` and a few letters list what you may mention, by kind; choosing writes the mention - or, after `[your own words](@`, only its address ([#469](https://github.com/arnecoomans/fmly/issues/469))
- **Mentions** - `[Eric](person:…)` in a biography, description, note or comment links to that person, item, event, place or note - only for who may see it; anyone else sees the text, a person's name as initials ([#468](https://github.com/arnecoomans/fmly/issues/468))
- **Preferences save themselves** - each change is saved at once, with "Saved" to confirm; a new language reloads the page in it ([#461](https://github.com/arnecoomans/fmly/issues/461))
- **Loose end: events without documentation** - the events with people that no item proves yet, each person's together, with a bar for how many are proven
- **PDF previews** - a PDF's first page as its thumbnail in lists, on the dashboard and in pickers, made on upload (pypdfium2); the thumbnail crop works on it too
- **Event title** - one field for what an event was or what it's called (it used to be title *and* own label, which held the same text); not asked for births, deaths, marriages and divorces; the new-event dialog says "unknown" for the place only once one's removed, and takes the item documenting it
- **Residence** - an event for proof someone lived somewhere without knowing when they moved there, from a source outside the archive ([#465](https://github.com/arnecoomans/fmly/issues/465))
- **History on the timeline** - a historical event can be *background for* another event: its people see it on their timeline, and it no longer shows for everyone; people linked to a historical event don't hide it from others; *with historic events / own events* on the timeline, remembered ([#464](https://github.com/arnecoomans/fmly/issues/464))
- **Add content from a person's page** - in edit mode, files dropped there become drafts already linked to that person; a file in the archive already gets them linked ([#456](https://github.com/arnecoomans/fmly/issues/456))
- **Photos & documents** - one kind of content for photos, documents, books, objects and recordings, with their parts; who is on a photo, dates and places, transcripts with OCR
- **Events and places** as pages of their own, linking people and content
- **Favorites** - a heart on an item's page, shared: who favorited it, family favorites on the dashboard, your own list, and a *most favorited* sort ([#453](https://github.com/arnecoomans/fmly/issues/453))
- **Research** - notes with questions, leads and conclusions; one search across everything, including transcripts and biographies, ignoring accents (Riede finds Riedé); comments
- **Edit mode** - change things on the page itself; every change in the admin history
- **Privacy** - community-visible by default, family-visible and private where needed, drafts until published; no external services, everything loaded from the site itself

### Under the hood
- Built on **cmnsd 3** (git submodule, branch `fmly`): models with status and visibility, an API, edit mode and cmnsd.js - see `cmnsd/documentation/`
- Django 6, Python 3.14; files served through Django's access checks (sendfile with nginx); static files with hashed names
- Settings from `.env` - template: `.env.example`; mail through SMTP with `EMAIL_URL` (password resets, registrations)
- `manage.py gedcom_export <token> --depth N`: one person and N levels of partners and children as GEDCOM 5.5.1 - living people as initials, private people and outsiders left out ([#463](https://github.com/arnecoomans/fmly/issues/463), the download and the whole tree to follow)
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
