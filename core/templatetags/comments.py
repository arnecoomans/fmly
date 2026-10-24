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


@register.filter
def comment_visibility(target):
  """{% with visibility=target|comment_visibility %} - {'default', 'choices'}
  for a comment on `target`: its visibility, and every level up to it - a
  comment is never more visible than what it's on (issue #481)."""
  from core.models import comment_visibility_for
  default, choices = comment_visibility_for(target)
  return {'default': default, 'choices': choices}


@register.filter
def comment_visibility_choices(comment):
  """The levels a comment can be set to: up to what it's on - plus its own,
  when it's wider than that now (the item was narrowed after it): opening
  the choice mustn't narrow it unasked. The loose end "comments that don't
  fit their item" is where that's decided."""
  from core.models import comment_visibility_for
  _default, choices = comment_visibility_for(comment.target)
  if comment.visibility not in dict(choices):
    choices = [*choices, (comment.visibility, comment.get_visibility_display())]
  return choices


@register.filter
def wider_comments(obj, request):
  """Its comments more visible than it, as this viewer may see them (#481)."""
  return list(obj.wider_comments(request)) if hasattr(obj, 'wider_comments') else []


@register.filter
def narrower_comments(obj, request):
  """Its comments less visible than it that this viewer may widen (#481)."""
  return list(obj.narrower_comments(request)) if hasattr(obj, 'narrower_comments') else []
