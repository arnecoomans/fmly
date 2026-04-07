from django.db import models
from django.contrib.auth.models import User

from .tag import Tag
from cmnsd.models import BaseModel


class Group(BaseModel):
  title               = models.CharField(max_length=255, blank=True)
  description         = models.CharField(max_length=512, blank=True, null=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  tag                 = models.ManyToManyField(Tag, blank=True, related_name='groups')

  def __str__(self):
    title = self.title
    ''' Prepend title with tag if there is one tag set.
        If more tags are set, it would get too messy.
    '''
    if self.tag and self.tag.all().count() == 1:
      for tag in self.tag.all():
        title = f"{ tag }: { title }"
    ''' Append title with short description if set
    '''
    if self.description:
      title += ' (' + self.description[:32]
      if len(self.description) > 32:
        title += '...'
      self.title += ')'
    return title

  def count_images(self):
    return self.images.exclude(status='x').count()
