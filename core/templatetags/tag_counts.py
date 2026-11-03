from django import template

from core.tags import attach_content_counts, visible_path
from core.tags import visible_parent as _visible_parent

register = template.Library()


@register.filter
def with_content_count(tag, request):
  """{% with tag=tag|with_content_count:request %} - one tag with its
  content count attached (core/tags.py), for a chip rendered on its own -
  e.g. the chip an edit-mode action returns."""
  return attach_content_counts([tag], request)[0]


@register.filter
def visible_parent(tag, request):
  """{% with parent=tag|visible_parent:request %} - the tag's parent if this
  viewer may see it, else None: a parent they may not see doesn't exist
  for them (core/tags.py visible_path)."""
  return _visible_parent(tag, request)


@register.filter
def visible_ancestors(tag, request):
  """{{ tag|visible_ancestors:request }} - the tags above it this viewer
  may see, top first (its page's path)."""
  return visible_path(tag, request)[:-1]
