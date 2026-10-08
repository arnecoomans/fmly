from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.fields import GenericRelation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from cmnsd.api.registry import api_action, api_model
from cmnsd.models.access import filter_accessible

from cmnsd.models import BaseTag, BaseComment, BasePreferences
from cmnsd.models.mixins import (
  TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin,
  VisibilityMixin, SearchableMixin
)

# In the API for the tag picker (edit mode): GET api/tag/?q=...&format=picker.
@api_model(search_fields=['name'])
class Tag(TimestampMixin, StatusMixin, VisibilityMixin, SearchableMixin, BaseTag):
  def get_absolute_url(self):
    """tags/<token>/<slug>/ - the token finds the tag (a slug is only
    unique within its parent, e.g. two 'boot' tags), the slug is for
    reading; token-only or outdated slugs redirect (TagDetailView)."""
    from django.urls import reverse
    return reverse('core:tag_detail', kwargs={'token': self.token, 'slug': self.slug or 'tag'})

  # Edit mode (cmnsd object_form): the page shows tag/blocks/<name>.html.
  # Dotted: core/forms.py imports this module.
  api_edit_forms = {
    'name': 'core.forms.TagNameForm',
    'parent': 'core.forms.TagParentForm',
    'description': 'core.forms.TagDescriptionForm',
  }

  def save(self, *args, **kwargs):
    """A renamed tag gets a slug from its new name - the address reads
    right; the old one redirects (TagDetailView finds a tag by token). A
    moved tag (another parent) keeps its slug, unless a new sibling has it.
    An unchanged name keeps its slug, also one that doesn't match it (a tag
    from FMLY 2), and so does the "Loose end" tag, which is found by its
    slug (core.tags). Here, not in cmnsd's BaseTag: another project's tag
    addresses may rest on the slug alone."""
    if self.pk and self.name:
      from .tags import LOOSE_END_SLUG
      before = type(self).objects.filter(pk=self.pk).values_list('name', 'slug', 'parent').first()
      if before and before[1] != LOOSE_END_SLUG:
        if before[0] != self.name:
          self._split_compounded_name()   # "Media: Book" -> Book under Media, before the slug is made
          self.slug = self._free_slug()
        elif before[2] != self.parent_id and self._siblings().filter(slug=self.slug).exists():
          self.slug = self._free_slug()
    super().save(*args, **kwargs)

  def _free_slug(self):
    """slugify(name), unique among its siblings: -2, -3, ... when taken."""
    from django.utils.text import slugify
    base = slugify(self.name)[:58] or 'tag'
    siblings = self._siblings()
    slug, number = base, 2
    while siblings.filter(slug=slug).exists():
      slug, number = f'{base}-{number}', number + 1
    return slug

  def _siblings(self):
    return type(self).objects.filter(parent=self.parent).exclude(pk=self.pk)

  # Django doesn't merge Meta across multiple abstract base classes - without
  # this, Tag silently picks up TimestampMixin's (empty) Meta instead of
  # BaseTag's, losing its ordering AND its parent-scoped UniqueConstraints.
  # TimestampMixin/StatusMixin/VisibilityMixin/SearchableMixin all define
  # Meta as just `abstract = True` - nothing of theirs is lost here.
  class Meta(BaseTag.Meta):
    pass

COMMENT_MAX_LENGTH = 5000


@api_model()
class Comment(VisibilityMixin, BaseComment):
  """A comment on any object (GenericForeignKey, BaseComment). Visibility
  of its own, on top of the item's: a comment shows only where the viewer
  may see both. Status: published on creation; the author deletes their
  own (status x - kept, shown to no one); staff hide any (revoked - still
  visible to staff, so it can be unhidden).

  Written through the API: the actions below and CommentableMixin's
  add_comment (cmnsd/views/api/object_action.py)."""

  class Meta(BaseComment.Meta):
    # Oldest first - a comment thread reads as a conversation.
    ordering = ['date_created']

  def get_absolute_url(self):
    """Where it's shown: its target's page, at this comment (comment/
    comment.html's id) - the admin's "view on site". The target's page
    checks access as always."""
    target = self.target
    url = target.get_absolute_url() if target is not None and hasattr(target, 'get_absolute_url') else None
    return f'{url}#comment-{self.token}' if url else None

  @classmethod
  def filter_own(cls, queryset, request=None):
    """Status and its own visibility only, not its target's - for a thread
    on a page the viewer already opened (CommentableMixin.get_visible_comments):
    the page decided about the target, e.g. a deleted item staff may open."""
    return super().filter_visibility(cls.filter_status(queryset, request), request)

  @classmethod
  def filter_visibility(cls, queryset, request=None):
    """Its own visibility (VisibilityMixin), and only on targets this
    viewer may see (status + visibility) - everywhere comments are read:
    a thread, the comment list, the API. Per target model: a couple of
    queries, not one per comment."""
    from django.contrib.contenttypes.models import ContentType
    queryset = super().filter_visibility(queryset, request)
    allowed = models.Q(pk__in=[])
    for content_type in ContentType.objects.filter(pk__in=queryset.values('target_content_type')):
      model = content_type.model_class()
      if model is None:
        continue
      targets = filter_accessible(model.objects.all(), request)
      allowed |= models.Q(target_content_type=content_type, target_id__in=targets.values('pk'))
    return queryset.filter(allowed)

  def is_edited(self):
    return (self.date_modified - self.date_created).total_seconds() > 60

  def _require_author(self, request):
    if not (request.user.is_authenticated and request.user.pk == self.user_id):
      raise PermissionDenied(_("Only the author can change this comment."))

  @api_action(requires_auth=True)
  def edit_comment(self, request, data):
    self._require_author(request)
    self.content = clean_comment_text(data.get('content'))
    self.save()
    messages.success(request, _("Comment saved."))
    return {'comment': self}

  @api_action(requires_auth=True)
  def delete_comment(self, request, data):
    self._require_author(request)
    self.status = self.Status.DELETED
    self.save()
    messages.success(request, _("Comment deleted."))
    return {'comment': self}

  @api_action(requires_auth=True)
  def toggle_hidden(self, request, data):
    """Staff: hide (revoked) or unhide (published) any comment."""
    if not request.user.is_staff:
      raise PermissionDenied(_("Only staff can hide comments."))
    self.status = self.Status.PUBLISHED if self.status == self.Status.REVOKED else self.Status.REVOKED
    self.save()
    messages.success(request, _("Comment hidden.") if self.status == self.Status.REVOKED else _("Comment visible again."))
    return {'comment': self}


def clean_comment_text(text):
  text = (text or '').strip()
  if not text:
    raise ValidationError(_("A comment can't be empty."))
  if len(text) > COMMENT_MAX_LENGTH:
    raise ValidationError(_("A comment can be at most %(max)s characters.") % {'max': COMMENT_MAX_LENGTH})
  return text


class CommentableMixin(models.Model):
  """Comments on a model: the relation, the list a viewer may see, and the
  add_comment API action. For Content now, Person next - any model that
  composes this gets the same comment thread (core/templates/comment/)."""

  comments = GenericRelation(Comment, content_type_field='target_content_type', object_id_field='target_id')

  class Meta:
    abstract = True

  @classmethod
  def comment_targets(cls, queryset):
    """Which of these objects may appear as a comment's target in the
    comment list (core/comments.py) - on top of status and visibility.
    Default: all. Person excludes private people (no page to link to)."""
    return queryset

  def get_visible_comments(self, request):
    """Status + visibility of each comment itself (Comment.filter_own): the
    viewer's own concept, staff's revoked, nobody's deleted. Not the
    target's again - that's this object, which the viewer already has open
    (also a deleted item staff may open: its comments show there)."""
    return Comment.filter_own(self.comments.select_related('user'), request)

  @api_action(requires_auth=True)
  def add_comment(self, request, data):
    """Only reachable when the viewer may see this object - the action
    dispatcher looks it up in the visible queryset first. Needs
    core.add_comment (the Visitors group, core prepare_release)."""
    if not request.user.has_perm('core.add_comment'):
      raise PermissionDenied(_("You can't comment."))
    comment = Comment(
      target=self, user=request.user, content=clean_comment_text(data.get('content')),
      status=Comment.Status.PUBLISHED,
    )
    comment.save()
    messages.success(request, _("Comment posted."))
    return {'comment': comment}

class Preferences(BasePreferences):
  # Read by VisibilityMixin.filter_visibility()/is_visible_to() via
  # CMNSD_VISIBILITY_FAMILY_LOOKUP_STORAGE = 'user__preferences__family'
  # (settings.py) - a per-user, one-directional "I consider this person
  # family" declaration, not necessarily symmetric. Same shape as cmpng's
  # own UserPreferences.family, which this setting's path was copied from.
  family = models.ManyToManyField(
    settings.AUTH_USER_MODEL, blank=True, related_name='family_of',
    help_text=_("Users to treat as family for 'family'-visibility content"),
  )
