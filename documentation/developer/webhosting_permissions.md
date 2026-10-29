# Web hosting: running as its own user

Which system user the site runs as, and what it may write. Part of [Web hosting](webhosting.md).

## Why

Whatever user gunicorn runs as is what an attacker gets if a flaw in the application lets them run code. For FMLY the realistic route is file parsing: every upload goes through Pillow (JPEG, PNG, TIFF, HEIC), pypdfium2 (PDF) and OCR - large C libraries reading files from outside.

| The site runs as… | A break-in reaches… |
|---|---|
| an admin's own account (with sudo) | that account: its SSH keys and home directory, every site it manages, and its sudo password the next time it logs in (planted in its shell startup) |
| `www-data`, shared by all sites | every site running as `www-data` |
| its own user (`fmly`) | fmly's files and database only |
| **its own user, the code not writable** | fmly's data - not its code: nothing survives a restart or an update |

The last row is the setup described here. No user separation protects fmly's own data from a flaw in fmly itself - the process has to read it; separation limits what lies *beyond* it, and how long an attacker can stay.

## The setup

- **The code is the admin's** (`arnecoomans`): the repository, `.venv`, `public/static`. `./update.sh` runs as that admin, as before - nothing to switch, nothing to forget.
- **The web process runs as `fmly`**, a system user without a login or sudo. It writes only:
  - `private/` - uploads (`MEDIA_ROOT`) and the thumbnail cache;
  - its socket, `/data/www/cmns.nl/run/fmly.sock`.
- **It reads** `.env` (group `fmly`, mode 640) and the code.
- **The group `fmly`** holds `www-data` (nginx serves files from `private/` and talks to the socket) and the admin (updates, `pato.sh`, `manage.py` commands that read uploads).
- **The database** is PostgreSQL, with its own credentials in `.env` - no database file to share.

## Moving to it

On the server, about ten minutes. Until step 4 the site keeps running as before.

**1. The user**, a system account - no login shell, no password, no home:

```
sudo adduser --system --group --no-create-home fmly
sudo usermod -aG fmly www-data        # nginx: files from private/, the socket
sudo usermod -aG fmly arnecoomans     # the admin: updates, pato.sh
```

Log out and in again for the admin's new group to take effect.

**2. What the web process writes, and reads:**

```
sudo chown -R fmly:fmly /data/www/fmly.cmns.nl/private
sudo chmod -R g+rwX /data/www/fmly.cmns.nl/private          # its group may read (nginx) and write (the admin's commands)
sudo chgrp fmly /data/www/fmly.cmns.nl/.env
sudo chmod 640 /data/www/fmly.cmns.nl/.env                  # the secret key and passwords: owner and group only
sudo chgrp fmly /data/www/cmns.nl/run
sudo chmod g+w /data/www/cmns.nl/run                        # for its socket
```

The rest stays the admin's.

**3. The start script** (`/data/www/cmns.nl/gunicorn/fmly_start`, see [Web hosting](webhosting.md)):

```bash
USER=fmly
GROUP=fmly
```

and add `--umask 007` to the gunicorn command: its socket and new uploads are then readable and writable by the group (nginx, the admin) and nobody else.

**4. supervisord** (`[program:fmly]`): `user = fmly`, then

```
sudo supervisorctl reread && sudo supervisorctl update && sudo supervisorctl restart fmly
```

**5. Check:**

```
ps -o user= -p $(pgrep -f "gunicorn.*fmly" | head -1)     # fmly
```

- open a page, and a photo - the file comes through nginx from `private/`;
- upload a file - written by `fmly`;
- run `./update.sh` as the admin - pulls, migrates, restarts as before.

**When something fails** it's almost always a permission: `sudo tail -n 50 /var/logs/gunicorn/fmly.log` names the file, `ls -l` shows its owner.

## Living with it

- **Updates:** `./update.sh` as the admin, unchanged. It never writes in `private/` - `.post_update.sh`'s commands read uploads (checksums), which the admin may as a member of the group.
- **New files in `private/`** are written by `fmly` with the group `fmly` and, thanks to `--umask 007`, group read/write: nginx serves them, the admin's commands read them.
- **`manage.py` commands that write uploads** (renaming stored files, purging in Housekeeping runs in the web process anyway): run them as the site user - `sudo -u fmly .venv/bin/python manage.py …` - so new files belong to `fmly`.
- **`pato.sh`** pulls `private/` over SSH as the admin: it reads, which the group allows.
- **Other sites** on the server: the same, each with its own user - a flaw in one then doesn't reach the others.
- **Never** add `fmly` to sudo, and don't give it a login shell.
