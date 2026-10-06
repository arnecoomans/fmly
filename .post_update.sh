#!/bin/bash
# fmly: site-specific steps after every update. Run by update.sh
# (cmnsd/resources/update.sh, symlinked in the project root) with the
# virtual environment active, just before the restart. UPDATE_CHANGED=1
# when the pull brought changes. Each step is safe to repeat.
set -e

# Default pages a new release adds - existing ones (edited in the admin) are left alone.
python manage.py create_default_pages

# Checksums and dimensions of files that don't have them yet (new uploads have them already).
python manage.py content_checksums

# Warnings worth seeing after an update, e.g. a missing OCR language.
python manage.py check
