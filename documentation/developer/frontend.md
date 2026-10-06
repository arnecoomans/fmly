# Frontend

FMLY3's pages are server-rendered Django templates, styled with plain CSS and enhanced by cmnsd.js. There's no build step: what's in the repository is what the browser gets (after `collectstatic` hashes the names).

## Templates

`templates/base.html` is every page's frame. Its blocks:

| Block | For |
|---|---|
| `title` | The page title |
| `template_css` | A page's own stylesheet (`person.css`, `content.css`) |
| `content` | The page |
| `template_js` | A page's own script - rare; prefer a cmnsd.js module |

The header (`templates/header.html`, `navigation.html`) and footer are included by it.

Naming conventions in the apps:

| Template | Is |
|---|---|
| `<model>/blocks/<block>.html` | An edit block as read (cmnsd edit mode) |
| `<model>/forms/<block>.html` | Its form, when the generic one doesn't fit |
| `<model>/<model>_list.html`, `_picker.html` | Rendered by the cmnsd API for live lists and pickers |
| `<model>/<model>_overview.html` | A page listing them - not `_list.html`, which the API uses |
| `person/functions/<method>.html` | A rendered model method, e.g. `get_full_name.html` |
| `_<name>.html` | A partial, included by others |

Every template starts with a `{% comment %}` saying what it shows, where it's used and what context it needs.

## CSS

`static/css/fmly/`, loaded in this order:

1. **`specs.css`** - the design tokens: colours (`--color-ink`, `--color-accent` ...), type sizes (`--text-sm` ...), spacing, radii, `--topbar-height`. Use tokens, never raw values.
2. **`base.css`** - elements and the page shell.
3. **`components.css`** - everything shared: header, buttons, cards, edit blocks, dialogs, the lightbox, dashboard blocks.
4. **`person.css`**, **`content.css`** - per page, through `template_css`.

Class names follow BEM: `block__element--modifier` (`person-row__name`, `btn--sm`). Narrow screens are handled in the same files with `max-width` media queries; the header goes to icons only below 800 px.

Icons are Bootstrap Icons (`<i class="bi bi-..."></i>`); Bootstrap itself is loaded but FMLY3's components don't depend on it.

## cmnsd.js

Started in `base.html`:

```js
cmnsd.init({ apiRoot: '/api/', sectionStateUrl: ..., sortStateUrl: ..., debug: ... });
```

Templates switch features on with data attributes - `data-cmnsd-list-url`, `data-cmnsd-edit-block`, `data-cmnsd-upload`, `data-cmnsd-lightbox`, `data-cmnsd-hint` and so on. Each module documents its attributes at the top of its file (`cmnsd/static/cmnsd.js/`).

Rules:

- **Every page works without JavaScript.** A live search is a plain GET form first; an upload a plain form; the lightbox a link to the file.
- **Templates add the attributes only when `load_on_ready` is on** (`CMNSD_LOAD_ON_READY`), the kill switch for all enhancements.
- **New behaviour goes into a cmnsd.js module** when it's generic, not into an inline script.

## The HTML minifier

cmnsd's output middleware minifies every page. Two consequences:

- Attribute quotes are dropped where possible - tests compare with `html.replace('"', '')`.
- An empty `value=""` is dropped: a radio button needs a non-empty value, or the browser sends `on`.
