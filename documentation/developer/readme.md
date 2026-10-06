# FMLY3 developer documentation

For whoever installs, runs or develops FMLY3. For using the archive, see [Using FMLY3](../usage/readme.md).

## Contents

Read in this order when you're new; each page stands on its own afterwards.

| Page | What it covers | Status |
|---|---|---|
| [Installation](installation.md) | From a fresh clone to a running archive: code, requirements, data | written |
| [Configuration](configuration.md) | The `.env` settings | written |
| [Web hosting](webhosting.md) | gunicorn, supervisord and nginx | written |
| [Deploying](deploying.md) | `update.sh` and `.post_update.sh` for every update, the checks | written |
| [cmnsd](cmnsd-dependency.md) | The shared foundation: what it provides, what stays in FMLY3, working on the submodule | written |
| [Architecture](architecture.md) | The apps (core, people, content, events, places, notes, dashboard, legacy_import), how a request flows, where things live | written |
| [Visibility and access](visibility-and-access.md) | Status and visibility, family, private people, staff, drafts - and `filter_accessible` everywhere | written |
| [Data model](data-model.md) | People and relations, content and its parts, events, places, notes, tags | written |
| [The legacy import](legacy-import.md) | `import_all` and its steps, re-running, `import_content --files-only` | written |
| [Management commands](management-commands.md) | `content_checksums`, `prepare_release`, `create_default_pages`, the importers | written |
| [Frontend](frontend.md) | Templates, CSS (tokens, components), cmnsd.js on FMLY3's pages | written |
| [Testing](testing.md) | Running the suite, test data, temporary media - never the real `private/` | written |

## How a developer page looks

**One topic per page**, named after the topic in lowercase with hyphens (`visibility-and-access.md`), and listed in the table above.

**Structure:**

1. A title, then one or two sentences: what this is and when you need it.
2. Sections in the order someone needs them - setup before use, the common case before the exceptions.
3. Code blocks for commands and settings, so they can be copied as they are.
4. Links to the code (`people/privacy.py`) rather than copies of it: the code is the detail, the page is the map.

**Keep it:**

- **Short** - under 100 lines. When a page grows past that, it's two topics.
- **True** - written for what's built, not what's planned. Plans and the backlog live in `docs/` (development notes), not here.
- **In step with the code** - a change that makes a page wrong updates the page in the same commit.
- **Free of private data** - no real family names, account names, server passwords or paths that aren't examples. Use `fmly.example.org` and invented names.

**Write for someone new to FMLY3 but not to Django**: explain FMLY3's choices and conventions (why visibility is checked where it is, why cmnsd stays generic), not Django itself.

## Related

- `docs/` - development-stage notes: plans, decisions, the backlog (`docs/issues.md`)
- `cmnsd/documentation/` - cmnsd's own documentation
