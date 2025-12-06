from django.urls import reverse_lazy

from cmnsd.models.Tag import Tag

class Tag(Tag):
  class Meta:
    ordering = (['name'])
  
  def get_absolute_url(self):
    return reverse_lazy('archive:tags')
  
  def get_images(self):
    return self.images.all().filter(visibility_frontpage=True)
  def get_hidden_images(self):
    return self.images.all().filter(is_deleted=False, visibility_frontpage=False)