from datetime import date

from django import template
from django.utils.translation import ngettext

register = template.Library()


@register.filter
def years_ago(event):
  """{{ event|years_ago }} -> '113 years ago' - from the event's year to this
  year; for an uncertain date 'about' (circa), 'at least' (before: it may be
  longer ago) or 'at most' (after). Unlike an age, a bound reads as a fact
  here, not a judgement (people/timeline.py age_at leaves those out)."""
  if not getattr(event, 'year', None):
    return ''
  years = date.today().year - event.year
  qualifier = getattr(event, 'date_qualifier', 'exact')
  if qualifier == 'circa':
    return ngettext("about %(n)s year ago", "about %(n)s years ago", years) % {'n': years}
  if qualifier == 'before':
    return ngettext("at least %(n)s year ago", "at least %(n)s years ago", years) % {'n': years}
  if qualifier == 'after':
    return ngettext("at most %(n)s year ago", "at most %(n)s years ago", years) % {'n': years}
  return ngettext("%(n)s year ago", "%(n)s years ago", years) % {'n': years}
