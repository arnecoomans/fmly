from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from cmnsd.api.registry import api_model
from cmnsd.models.mixins import (
  TimestampMixin, TokenMixin, OwnershipMixin, HierarchyMixin, SlugMixin, EditableRelationsMixin,
)


# In the API for the place picker (edit mode): GET api/place/?q=...&format=picker.
# No status or visibility - readable by anyone (place names already show on
# public items; docs/EDIT-MODE-PLAN.md).
@api_model(search_fields=['name', 'alias'])
class Place(TimestampMixin, TokenMixin, SlugMixin, OwnershipMixin, HierarchyMixin, EditableRelationsMixin, models.Model):
  name = models.CharField(max_length=255)
  alias = models.CharField(
    max_length=255, blank=True,
    help_text=_("Alternate spelling/language for the same place at the same time - e.g. Indonesië / Indonesia"),
  )
  alternatives = models.ManyToManyField(
    'self', blank=True,
    help_text=_("Other Place records for the same location in a different era - e.g. Batavia / Jakarta"),
  )
  # parent (self-FK, PROTECT), compound-name splitting, display_name() and
  # ancestors() all come from HierarchyMixin.

  latitude = models.FloatField(null=True, blank=True)
  longitude = models.FloatField(null=True, blank=True)

  description = models.TextField(blank=True)

  # The URL is led by the token (places/<token>/<slug>/), so the slug may
  # follow a rename - an old address redirects (PlaceDetailView).
  slug_follows_source = True

  # Edit mode (cmnsd object_form): name -> the form (dotted: places/forms.py
  # imports this model). The page shows place/blocks/<name>.html.
  api_edit_forms = {
    'name': 'places.forms.PlaceNameForm',
    'alias': 'places.forms.PlaceAliasForm',
    'parent': 'places.forms.PlaceParentForm',
    'description': 'places.forms.PlaceDescriptionForm',
  }

  # Edit mode: the same location in another era (EditableRelationsMixin -
  # link/unlink). Symmetrical: Batavia's alternative Djakarta has Batavia.
  api_editable_relations = {
    'alternatives': {'create': {}},
  }

  class Meta:
    ordering = ['name']

  def __str__(self):
    return self.name

  def get_slug_source(self):
    return self.name

  def get_absolute_url(self):
    """places/<token>/<slug>/ - the token finds the place, the slug is for
    reading; a token-only or outdated address redirects here."""
    if not self.slug:
      return reverse('places:detail_by_token', kwargs={'token': self.token})
    return reverse('places:detail', kwargs={'token': self.token, 'slug': self.slug})

  def get_list_url(self):
    return reverse('places:list')

  def clean(self):
    super().clean()
    # A parent may not be the place itself or lie below it - that would
    # make a loop (Java under Batavia under Java).
    node = self.parent
    while node is not None:
      if self.pk and node.pk == self.pk:
        raise ValidationError({'parent': _("A place can't lie within itself or one of its own places.")})
      node = node.parent

  def save(self, *args, **kwargs):
    self._split_compounded_name()
    self.full_clean()
    super().save(*args, **kwargs)
