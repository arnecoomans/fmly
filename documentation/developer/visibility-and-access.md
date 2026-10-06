# Visibility and access

Privacy is FMLY3's first rule: nothing is shown before it's checked who may see it. This page explains the rules and where they're applied.

## Two checks: status and visibility

Every archive object has a **status** and most a **visibility** (cmnsd's `StatusMixin` and `VisibilityMixin`).

| Status | Seen by |
|---|---|
| published | everyone the visibility allows |
| draft (*concept*) | its owner, and staff |
| revoked | staff |
| deleted | nobody - except staff on the item's own page (`Content.objects.viewable_by`) |

| Visibility | Seen by |
|---|---|
| public | everyone, also signed out |
| community | every signed-in account |
| family | the owner, and the accounts in the owner's family list (`Preferences.family`) |
| private | the owner |

"Family" is per owner and one way: it's the list the *owner* chose in their preferences.

## Applying them

**`filter_accessible(queryset, request)`** (`cmnsd/models/access.py`) applies both. Use it - or a model's own `visible_to(request)` - every time objects are shown: lists, pages, pickers, search, counts, the API. A count over unfiltered rows leaks that something exists.

Models can refine the rule:

- **Events** have no visibility of their own: an event is visible when one of its people is, or when it has no people (history).
- **Comments** have their own visibility *and* need a visible target. On a page the target is already checked, so a thread only filters the comments themselves (`Comment.filter_own`).
- **Private people** (`Person.private`, `people/privacy.py`): their name shows, their page opens only for themselves, their parents and staff. `Person.page_url_for(user)` and the `person_url` filter decide per viewer; `get_absolute_url()` stays empty for them.

## Showing names

A person can be visible on one page while a relative isn't. Names always go through a template or filter that checks: `person/functions/get_full_name.html` shows an obfuscated name for a hidden person, `|viewer_name` does the same for any object, and `event_display` names only an event's visible people. Never print `{{ person }}` or `{{ event }}` directly.

## Who may change what

- **Edit mode** is for accounts with at least one change permission (`cmnsd/edit/mode.py`). Each object then decides with `can_edit(user)`, or the model's change permission.
- **Groups** (made by `prepare_release`): **Visitors** may comment, **Editors** may add and change the archive. Nobody deletes rows from the site - deleting is a status.
- **Staff** also see others' drafts, deleted items (on their page) and, with the right permissions, *Housekeeping* and *Accounts*.

## Checklist for a new view or endpoint

1. Start from `filter_accessible` (or `visible_to`), never `Model.objects.all()`.
2. Answer 404 for hidden and missing alike - never 403 for something hidden.
3. Show names through the name templates and filters.
4. Check related objects too: a visible photo can show a hidden person.
5. Write a test with a viewer who may *not* see it.
