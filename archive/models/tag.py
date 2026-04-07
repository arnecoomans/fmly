from django.db import models
from django.db.models import Count
from django.urls import reverse_lazy

from cmnsd.models.Tag import Tag


class TagQuerySet(models.QuerySet):
  """Custom queryset for Tag — adds chainable optimisation methods."""

  def with_counts(self):
    """Annotate each tag with the number of related images."""
    return self.annotate(image_count=Count('images', distinct=True))


class TagManager(models.Manager):
  """Default manager for Tag. Returns TagQuerySet instances."""

  def get_queryset(self):
    return TagQuerySet(self.model, using=self._db)

  def with_counts(self):
    return self.get_queryset().with_counts()


class Tag(Tag):
  objects = TagManager()

  class Meta:
    ordering = (['name'])
  
  def get_absolute_url(self):
    return reverse_lazy('archive:tags')
  
  def get_images(self):
    return self.images.all().filter(visibility_frontpage=True)
  def get_hidden_images(self):
    return self.images.all().filter(is_deleted=False, visibility_frontpage=False)