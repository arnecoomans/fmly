from django import template

register = template.Library()


@register.filter
def visible_comments(target, request):
  """{% with comments=item|visible_comments:request %} - the comments on
  a CommentableMixin object that this viewer may see (status + each
  comment's own visibility)."""
  return target.get_visible_comments(request)


@register.filter
def model_name(obj):
  """{{ target|model_name }} -> 'content', 'person', ... - which kind of
  object a comment is on, to render its header (comment/_target.html)."""
  return obj._meta.model_name
