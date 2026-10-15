# Architecture

How FMLY3 is put together: the apps, what each owns, and how a request flows. Read [cmnsd](cmnsd-dependency.md) first for the shared foundation underneath.

## The apps

| App | Owns | Main addresses |
|---|---|---|
| `core` | Tags, comments, preferences, search, the release command | `/search/`, `/tags/`, `/comments/`, `/preferences/` |
| `people` | Persons and their relations, the timeline, private people | `/people/`, `/person/<token>/<slug>/` |
| `content` | Photos, documents, books, objects, recordings; files, thumbnails, transcripts, portraits, the inbox | `/content/`, `/content/<token>/<slug>/` |
| `events` | Events (births to history), the calendar | `/events/`, `/events/calendar/` |
| `places` | Places within places | `/places/` |
| `notes` | Research notes | `/notes/` |
| `dashboard` | The start page, loose ends, housekeeping, accounts | `/`, `/dashboard/...` |
| `fmly` | Settings and the root URL configuration | |

Apps depend on each other where the domain does - content knows people, events know people and places - but none of them on `dashboard`, which only reads.

## A request

1. **Middleware** (`fmly/settings.py`): sessions, CSRF, authentication, the user's language (cmnsd), messages, and finally cmnsd's HTML output middleware, which minifies every HTML response.
2. **A view** - mostly class-based. Every view that shows objects narrows them first with status and visibility (see [Visibility and access](visibility-and-access.md)); a hidden object and a missing one both answer 404.
3. **A template** - `templates/base.html` with the header, then the app's own templates. Object names go through templates that know what this viewer may see (`person/functions/get_full_name.html`, `|viewer_name`).
4. **cmnsd.js** enhances the page in the browser: live search, edit blocks, uploads. Behind it is the cmnsd **API** (`/api/...`): the same models, the same visibility rules, answering JSON.

## Pages and the API, side by side

Most interactive parts exist twice on purpose: a plain page or form that works without JavaScript, and an API endpoint that cmnsd.js uses to do the same in place. Both use the same querysets and forms, so they can't disagree. A model opts into the API with `@api_model`; what it exposes is listed explicitly - its fields, its actions, its edit forms (`api_edit_forms`) and its searchable fields.

## Where things live

| Kind of code | Place |
|---|---|
| Models | `<app>/models.py` or `<app>/models/` (one file per model in people and content) |
| Rules that span models | a module named after the rule: `people/privacy.py`, `people/timeline.py`, `content/portraits.py`, `dashboard/blocks.py` |
| Forms, edit blocks | `<app>/forms.py`; block templates in `<app>/templates/<model>/blocks/` |
| Management commands | `<app>/management/commands/` |
| Shared templates and the header | `templates/` |
| CSS | `static/css/fmly/` (see [Frontend](frontend.md)) |
| Files of the archive | `private/` - never served directly |

## Storage

- **Database:** SQLite by default (`DATABASE_URL`).
- **Files:** `private/content/<year>/` - uploads and imported files, named after the item when the original name says nothing (`content/files.py`). Thumbnails are cached in `private/cache/`.
- **Static files:** collected into `public/static/` with hashed names.

## Design principles

**Don't administer by hand what's logged automatically - and don't derive automatically what can easily be managed by hand.**

- *Logged automatically:* who changed what and when (the admin history, `log_change`), who favorited an item, uploads and their checksums, dates in files. Nobody should have to keep these up to date themselves.
- *Managed by hand:* what the data *means* - who was where, what an item is evidence of, which history matters to whom. Derived from links that don't say *how* someone is connected, it guesses - and a timeline that guesses wrong is worse than one that shows less. Derived "seen in" was built and removed for this reason ([#465](https://github.com/arnecoomans/fmly/issues/465)): a postcard addressed to someone isn't proof they were there.
- *The test case - parents and siblings:* parents are entered by hand, siblings are derived (`get_siblings`). That works one way only: sharing one parent makes two people siblings - half-siblings if they share only one - but knowing two people are siblings doesn't say they share *all* their parents. So siblings follow safely from parents, and parents can't follow from siblings: they're recorded by hand.
- In between: **suggest, and let a person decide** - a loose end or a hint that proposes ("residence suggestions"), with one click to record it and one to dismiss it. And where meaning is recorded explicitly (a *background for* link, an item linked to an event), derive from that freely: the decision was made by hand.
