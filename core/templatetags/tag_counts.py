from django import template

from core.tags import attach_content_counts

register = template.Library()


@register.filter
def with_content_count(tag, request):
  """{% with tag=tag|with_content_count:request %} - one tag with its
  content count attached (core/tags.py), for a chip rendered on its own -
  e.g. the chip an edit-mode action returns."""
  return attach_content_counts([tag], request)[0]
