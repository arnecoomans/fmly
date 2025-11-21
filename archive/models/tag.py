from django.db import models
from django.urls import reverse_lazy
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User

from cmnsd.models.Tag import Tag

class Tag(Tag):
  class Meta:
    ordering = (['name'])
  
  # Save all tags as lowercase. Use |title in the template for displaying  
  # def save(self, *args, **kwargs):
  #   self.name = self.name.lower()
  #   self.slug = slugify(self.name)
  #   return super(Tag, self).save(*args, **kwargs)

  def get_absolute_url(self):
    return reverse_lazy('archive:tags')
  
  def get_images(self):
    return self.images.all().filter(visibility_frontpage=True)
  def get_hidden_images(self):
    return self.images.all().filter(is_deleted=False, visibility_frontpage=False)
  # def get_images(self):
  #   return self.images.all().exclude(status="x").filter(visibility_frontpage=True)
  # def get_hidden_images(self):
  #   return self.images.all().exclude(status="x").filter(visibility_frontpage=False)