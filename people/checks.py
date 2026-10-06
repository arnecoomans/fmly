from django.core.checks import register, Error

ALLOWED_PREFIXES = ('person', 'people')


@register()
def check_url_prefixes(app_configs, **kwargs):
  """people.urls is mounted at the project root with no wrapping prefix
  (fmly/urls.py: path('', include('people.urls'))), so list vs. detail can
  use plural/singular grammar (people/ vs person/<slug>/) instead of both
  being forced under one shared prefix. The tradeoff: a pattern added here
  without its own person/people prefix competes directly against every
  other app's top-level routes, and - since people.urls is included first
  in fmly/urls.py - would silently win and shadow whatever else wanted
  that route, rather than erroring. This check catches a forgotten prefix
  at `manage.py check` time instead of as a request-time surprise."""
  from people.urls import urlpatterns

  errors = []
  for url_pattern in urlpatterns:
    route = str(url_pattern.pattern)
    if not route.startswith(ALLOWED_PREFIXES):
      errors.append(Error(
        f"people.urls pattern '{route}' doesn't start with 'person' or "
        "'people' - people.urls has no wrapping prefix (mounted at the "
        "project root in fmly/urls.py), so this pattern is unprotected "
        "against colliding with another app's top-level route.",
        id='people.urls.E001',
      ))
  return errors
