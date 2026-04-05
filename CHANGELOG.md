# Changelog

## [Unreleased]

## [26.04.1] - planned
- [Bugfix] `Person.timeline()` fired one DB query per family member — replaced per-member loops with a single Event query using `Q` objects and subqueries
- [Bugfix] `get_safe_slug()` on Image fired a DB query on every loop iteration — now fetches conflicting slugs upfront in a single query and checks against a set
- Deleting a Person cascades and deletes their portrait Image - now it sets the remote relation as NULL. Migration required.
- Add Django Debug Toolbar when `DEBUG=True` — auto-enabled via conditional block in `settings.py` and `urls.py`
- Implement `.env` for secure hosting — `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DATABASE_URL` moved out of `settings.py` into environment variables via `django-environ`; `settings.py` is now safe to commit; `.env.example` added as template
- Update cmnsd module to reflect changes made for cmpng
  - Implement improved naming and functionality of BaseModels
  - Implement improved naming of Mixins
  - Use newer version of Bootstrap CSS and JS
  - Use updated version of cmnsd.js
- Update translations
- Update requirements

## [26.04] - 2026-04-04

Long standing release.
