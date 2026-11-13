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
| `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE` | on, unless `DEBUG` | Cookies only over HTTPS: a session cookie never goes out on a plain `http://` request |
| `SECURE_HSTS_SECONDS` | `0` (none) | Browsers come back over HTTPS only, for this many seconds. It can't be taken back from a browser that has seen it: start with `3600`, raise to `31536000` (a year) once all is well. The redirect from `http://` is nginx's |
| `DATABASE_URL` | `db.sqlite3` in the project | Any database django-environ understands; PostgreSQL: `postgres://fmly:<password>@localhost:5432/fmly` (a password of letters, digits, `-` and `_` only - see below) |
| `SENDFILE_BACKEND` | `simple` (Django sends files itself) | `nginx` in production |
| `CMNSD_REGISTRATION_REQUIRES_APPROVAL` | `False` | `True`: registered accounts stay inactive until approved |
| `REGISTER_DEFAULT_GROUPS` | `Visitors` | The groups a new account joins (Visitors may comment) |
| `CMNSD_LOGIN_LINKS` | `False` | `True`: staff can mail someone a link that signs them in once, and the sign-in page offers *Mail me a login link*. Needs `EMAIL_URL` |
| `CMNSD_PROXY_COUNT` | `0` | `1` in production (behind nginx): the visitor's address comes from nginx's `X-Forwarded-For` - for the limit on password guesses and the log. Gunicorn on a unix socket sees none itself. It also lets Django trust nginx's `X-Forwarded-Proto`: a request over HTTPS is known as one, and addresses built for mail (login links) start with `https://` |
| `SITE_NAME`, `META_DESCRIPTION` | "A Family Archive" | Shown in titles and pages |
| `EMAIL_URL` | the console (mail in the log) | The mail server: `smtp+tls://user:password@host:587` or `smtp+ssl://user:password@host:465`. `@`, `/` and `:` in the user or password percent-encoded (`%40`, `%2F`, `%3A`) |
| `DEFAULT_FROM_EMAIL`, `REGISTRATION_NOTIFY_EMAIL` | - | Sender address - one the mail server may send from (SPF/DKIM of its domain), or it's marked as spam; who hears of a new registration |
| `CMNSD_LOAD_ON_READY` | `True` | `False` switches off the JavaScript enhancements (a kill switch) |

## PostgreSQL

The driver (`psycopg`) is in `requirements.txt`. A user and a database it owns - owner, so `migrate` may create tables:

```sh
sudo -u postgres createuser --pwprompt fmly
sudo -u postgres createdb --owner=fmly fmly
```

The password goes into `DATABASE_URL`, where `@ : / # %` would break the address. Generate one without them:

```sh
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Errors and logs

`LOGGING` in `fmly/settings.py` sends Django's warnings and errors - a 500 with its traceback - to stderr: under supervisord into the gunicorn log, with `runserver` into the terminal. cmnsd adds sign-ins and failed sign-ins. With `DEBUG=False` there's nowhere else a 500 shows up: no error emails are set up.

