# Deploying

Part of [Installation](installation.md): starting the site the first time, then every update.

## The first start

With the supervisord config in place (see [Web hosting](webhosting.md)):

```sh
sudo chmod +x /data/www/cmns.nl/gunicorn/fmly_start   # the start script must be executable
sudo mkdir -p /var/logs/gunicorn                        # supervisord won't start a program without its log folder

sudo supervisorctl reread           # shows "fmly: available"
sudo supervisorctl update           # adds the program and starts it
sudo supervisorctl status fmly      # RUNNING, with an uptime
sudo tail -n 50 /var/logs/gunicorn/fmly.log   # the reason, if it isn't running

sudo nginx -t                       # once the nginx server block is in place
sudo systemctl reload nginx
```

`reread` and `update` are only needed when the supervisord config itself changes; after that, `sudo supervisorctl restart fmly` restarts the app. A second site next to it (a test copy, say) gets its own name everywhere: program, start script, socket, log file and nginx `proxy_pass`.

Before anything is committed there's nothing for `update.sh` to pull: copy the code, then run the steps by hand - `pip install -r requirements.txt`, `migrate`, `collectstatic --noinput`, `./.post_update.sh` (with the venv active) and the restart.

## Every update

`update.sh` from cmnsd does the whole deploy. Link it into the project root once:

```sh
ln -s cmnsd/resources/update.sh update.sh
```

Then every deploy is:

```sh
./update.sh
```

It pulls the repository and the cmnsd submodule (on its `fmly` branch), installs the requirements when a requirements file changed, always runs `migrate` and `collectstatic`, runs `.post_update.sh`, and restarts the app with `sudo supervisorctl restart fmly` - the program named after the directory's first part (`fmly.cmns.nl` -> `fmly`).

`collectstatic` is needed every time: static files are stored with their content hash in their name (`cmnsd/storage.py`), so a changed file gets a new name and no browser keeps an old copy. Without it, pages fail with "Missing staticfiles manifest entry".

**`.post_update.sh`** (versioned in fmly, executable) holds FMLY3's own steps, run with the virtual environment active just before the restart - each safe to repeat:

- `create_default_pages` - pages a new release adds; pages edited in the admin are left alone
- `content_checksums` - checksums and dimensions of files that don't have them yet
- `check` - warnings worth seeing after an update, such as a missing OCR language

If a step fails, `update.sh` stops before the restart, so the running site keeps its last working state.

In development (`DEBUG=True`) static files keep their plain names and `runserver` serves them; no `collectstatic` needed. A browser may still cache an old copy of a changed script: hard reload, or "Disable cache" in the developer tools.

## Checks

```sh
.venv/bin/python manage.py check
```

warns about a missing OCR piece: `content.W001` no tesseract program, `content.W002` no pytesseract, `content.W003` language data missing. By hand:

```sh
tesseract --version
tesseract --list-langs          # nld must be listed
.venv/bin/python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

**If OCR stays unavailable:**

- *`tesseract` found in your shell but not by the app:* the app's process has a different `PATH`. On Ubuntu the package installs `/usr/bin/tesseract`, which every service sees; on macOS Homebrew uses `/opt/homebrew/bin`, fine for `runserver` from a terminal.
- *A language missing:* `tesseract --list-langs` doesn't show it - install its package.
- *pytesseract missing:* installed in another venv than the app's - `pip install -r requirements.txt` in the app's own venv.

Uploads need disk space for the largest file in the temp directory: Django streams an upload over 2.5 MB to a temporary file (`FILE_UPLOAD_TEMP_DIR`, default the system's).
