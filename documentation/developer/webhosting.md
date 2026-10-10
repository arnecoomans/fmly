# Web hosting

Production runs FMLY3 under gunicorn, kept running by supervisord, behind nginx. Part of [Installation](installation.md); the settings these refer to are in [Configuration](configuration.md).

## Gunicorn and Supervisord

Gunicorn start script:

```bash
#!/bin/bash

NAME="fmly"
DJANGODIR=/data/www/fmly.cmns.nl
VENVDIR=$DJANGODIR/.venv
SOCKFILE=/data/www/cmns.nl/run/fmly.sock
USER=[USER]
GROUP=[USER]
NUM_WORKERS=3
DJANGO_SETTINGS_MODULE=fmly.settings
DJANGO_WSGI_MODULE=fmly.wsgi

echo "Starting $NAME as `whoami`"

# Activate the virtual environment
cd $DJANGODIR
source $VENVDIR/bin/activate
export DJANGO_SETTINGS_MODULE=$DJANGO_SETTINGS_MODULE
export PYTHONPATH=$DJANGODIR:$PYTHONPATH

# Create the run directory if it doesn't exist
RUNDIR=$(dirname $SOCKFILE)
test -d $RUNDIR || mkdir -p $RUNDIR

# Start Gunicorn
# Programs meant to be run under supervisor should not daemonize themselves (do not use --daemon)
# --timeout 300: an upload of a large scan (up to ~1 GB) takes a while.
exec $VENVDIR/bin/gunicorn ${DJANGO_WSGI_MODULE}:application \
  --name $NAME \
  --workers $NUM_WORKERS \
  --timeout 300 \
  --user=$USER --group=$GROUP \
  --bind=unix:$SOCKFILE \
  --log-level=info \
  --log-file=-
```

Supervisord config:

```ini
[program:fmly]
command = /data/www/cmns.nl/gunicorn/fmly_start
user = [USER]
stdout_logfile = /var/logs/gunicorn/fmly.log
redirect_stderr = true
environment=LANG=en_US.UTF-8,LC_ALL=en_US.UTF-8
```

Starting it the first time: [Deploying](deploying.md#the-first-start).

## Nginx

```nginx
server {
  # IPv4 and IPv6 - without [::]:80 certbot's IPv6 check hits another site (404).
  listen 80;
  listen [::]:80;
  server_name fmly.example.org;

  # Uploads: one file per request, the largest scans close to 1 GB.
  # The default 1 MB refuses every scan ("413", "too large for the server").
  client_max_body_size 1100m;
  client_body_timeout 300s;

  # Static files carry their content hash in their name (collectstatic):
  # they never change, so they're cached for a year.
  location /static/ {
    alias /data/www/fmly.cmns.nl/public/static/;
    expires 1y;
    add_header Cache-Control "public, immutable";
  }

  # gunicorn down, restarting (update.sh) or too slow: nginx's own page,
  # straight from the repository (static/errorpages/50x.html) - Django
  # can't answer, so no template; it reloads itself after 20 seconds.
  error_page 502 503 504 /50x.html;
  location = /50x.html {
    root /data/www/fmly.cmns.nl/static/errorpages;
    internal;
  }

  # The archive's files (private/) are never served directly: Django checks
  # who may see a file, then hands it to nginx here (SENDFILE_BACKEND=nginx).
  location /protected/ {
    internal;
    alias /data/www/fmly.cmns.nl/private/;
  }

  location / {
    proxy_pass http://unix:/data/www/cmns.nl/run/fmly.sock;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 300s;
  }
}
```

Errors: Django answers 400, 403, 404 and 500 with its own pages (`handler*` in `fmly/urls.py`, templates in `cmnsd/templates/errorpages/`; a form open too long gets `403_csrf.html`). When gunicorn itself doesn't answer, nginx shows `static/errorpages/50x.html`.

There's deliberately no `location` for `private/` itself: the files are only reachable through `/protected/`, which only Django can send to.
