"""
The comment list (/comments/): every comment a viewer may see, across all
commentable models, newest first.

Which comments a viewer may see - their own status and visibility, and
their target's - is Comment.filter_visibility (core/models.py), the same
for a thread, this list and the API. On top of that, this list leaves out
targets a model excludes with comment_targets() (no private people: there
is no page to link to).
"""

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from cmnsd.models.access import filter_accessible

from .models import Comment


def visible_comment_feed(request, on=None):
  """Comments this viewer may see, newest first. `on`: only comments on
  this model (its model_name, e.g. 'content', 'person'); None = all."""
  comments = filter_accessible(Comment.objects.all(), request)
  allowed = Q(pk__in=[])
  for content_type in ContentType.objects.filter(pk__in=comments.values('target_content_type')):
    model = content_type.model_class()
    if model is None or (on and model._meta.model_name != on):
      continue
    if hasattr(model, 'comment_targets'):
      targets = model.comment_targets(model.objects.all())
      allowed |= Q(target_content_type=content_type, target_id__in=targets.values('pk'))
    else:
      allowed |= Q(target_content_type=content_type)
  return (
    comments.filter(allowed)
    .select_related('user', 'user__person', 'target_content_type')
    .prefetch_related('target')
    .order_by('-date_created')
  )
