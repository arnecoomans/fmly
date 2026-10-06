# Configuration (.env)

Part of [Installation](installation.md).

Settings come from `.env` in the project root (django-environ; never committed). For production:

```ini
SECRET_KEY=<a long random string - see below>
DEBUG=False
ALLOWED_HOSTS=fmly3.cmns.nl
CSRF_TRUSTED_ORIGINS=https://fmly3.cmns.nl
DATABASE_URL=sqlite:////path/to/fmly/db.sqlite3

# Files are served by nginx after Django checked access (see Web hosting: Nginx)
SENDFILE_BACKEND=django_sendfile.backends.nginx

# New accounts wait for approval by staff (Accounts, in the user menu)
CMNSD_REGISTRATION_REQUIRES_APPROVAL=True
REGISTER_DEFAULT_GROUPS=Visitors

SITE_NAME=FMLY
META_DESCRIPTION=An archive of a family's history, memories, and stories.
DEFAULT_FROM_EMAIL=noreply@fmly.example.org
REGISTRATION_NOTIFY_EMAIL=you@example.org
```

A new `SECRET_KEY`, for each site of its own:

```sh
.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

A copy of this file is in `.env.example`.

| Key | Default | What it does |
|---|---|---|
| `SECRET_KEY` | - (required) | Django's signing key |
| `DEBUG` | - (required) | `False` in production: hashed static file names, no debug toolbar |
| `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` | empty | The site's host name, and its `https://` origin |
| `DATABASE_URL` | `db.sqlite3` in the project | Any database django-environ understands |
| `SENDFILE_BACKEND` | `simple` (Django sends files itself) | `nginx` in production |
| `CMNSD_REGISTRATION_REQUIRES_APPROVAL` | `False` | `True`: registered accounts stay inactive until approved |
| `REGISTER_DEFAULT_GROUPS` | `Visitors` | The groups a new account joins (Visitors may comment) |
| `SITE_NAME`, `META_DESCRIPTION` | "A Family Archive" | Shown in titles and pages |
| `DEFAULT_FROM_EMAIL`, `REGISTRATION_NOTIFY_EMAIL` | - | Sender address; who hears of a new registration |
| `CMNSD_LOAD_ON_READY` | `True` | `False` switches off the JavaScript enhancements (a kill switch) |
