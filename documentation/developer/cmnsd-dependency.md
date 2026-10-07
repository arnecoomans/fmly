# cmnsd - the shared foundation

FMLY3 is built on **cmnsd**, a reusable Django app that holds everything that isn't specific to a family archive: the models' common behaviour, an API, edit mode, a JavaScript layer and the templates that go with them. It's included as a **git submodule** in `cmnsd/`, on the branch **`fmly`**.

```
fmly/
├── cmnsd/          the submodule - generic, shared
├── core/           FMLY3's own apps - tags, comments, preferences, search ...
├── people/  content/  events/  places/  notes/  dashboard/
└── fmly/           settings and urls
```

## The rule: generic in cmnsd, specific in FMLY3

- **cmnsd never imports FMLY3.** No `from people import ...`, no family logic, no FMLY3 settings beyond what it reads with `getattr(settings, ..., default)`.
- **Something goes into cmnsd when another project could use it unchanged** - a mixin, an API endpoint, a cmnsd.js module. Everything about families, people, content and their rules stays in FMLY3.
- **Project-specific behaviour hooks into cmnsd**, not the other way round: a model defines `api_search_q`, `api_edit_forms` or `can_edit`; a template sets a data attribute that cmnsd.js reads.

When in doubt, start in FMLY3. Move it into cmnsd once a second use shows what's generic about it.

## What FMLY3 takes from cmnsd

**Models** (`cmnsd/models/`)
- Mixins: `TimestampMixin`, `TokenMixin`, `SlugMixin`, `StatusMixin` (published, draft, revoked, deleted), `OwnershipMixin`, `VisibilityMixin` (public, community, family, private), `PartialDateMixin` (a date with unknown parts and *ca./before/after*), `HierarchyMixin` (parent and child), `EditableRelationsMixin`, `SearchableMixin`.
- Base models: `BaseTag`, `BaseComment`, `BasePreferences` - FMLY3's `Tag`, `Comment` and `Preferences` extend them in `core/models.py`.
- Concrete: `Page`, the multilingual site pages (cookie statement).
- `filter_accessible()` (`cmnsd/models/access.py`) - status and visibility in one call. Use it whenever a viewer gets to see objects.

**The API** (`cmnsd/api/`, `cmnsd/views/api/`) - models register with `@api_model`, fields with `@api_field`, actions with `@api_action`. Endpoints for lists and search, fields, actions, forms (edit blocks), creating, child records and suggestions, all visibility-checked. See `cmnsd/documentation/api.md` and `docs/api/` in FMLY3.

**Edit mode** (`cmnsd/edit/mode.py`) - the switch in the header, edit blocks (`cmnsd/edit/block.html`) and choice buttons, saved through the API; every change logged in the admin history.

**cmnsd.js** (`cmnsd/static/cmnsd.js/`) - plain ES modules, no build step. Each module enhances markup marked with `data-cmnsd-*` attributes: live lists and search, edit blocks and dialogs, pickers, uploads, the image viewer and lightbox, collapsible sections, messages. Without JavaScript every page still works.

**Templates and tags** - collapsible sections, edit blocks, `|markdown`, `{% highlight_search %}`, `|viewer_name` (a name as this viewer may see it).

**Also:** authentication pages (sign in, register with approval, profile), the user-language middleware, `ui_state` (remembered folds and sort orders), hashed static file storage (`cmnsd/storage.py`), and `resources/update.sh` (the deploy script, see [Deploying](deploying.md)).

## Working on cmnsd

cmnsd is its own git repository inside FMLY3:

```sh
cd cmnsd
git status                      # on branch fmly
git commit -am "..."            # commit in cmnsd first
git push                        # cmnsd's fmly branch
cd ..
git add cmnsd                   # then record the new cmnsd commit in FMLY3
git commit -m "Update cmnsd"
```

- A change to a cmnsd **model** needs a migration in `cmnsd/migrations/`.
- A change to **cmnsd.js** is picked up by `collectstatic` on the next deploy; `update.sh` always runs it.
- cmnsd has its own **tests** (`cmnsd/tests.py`); FMLY3's test suite runs them too.
- cmnsd's own documentation is in `cmnsd/documentation/` (start at `cmnsd/documentation/readme.md`).

## Other projects

cmnsd also runs under other projects on other branches. FMLY3's `fmly` branch is the most recent; the other branches will be brought onto it later, so changes made here should stay generic enough to be used there too.
