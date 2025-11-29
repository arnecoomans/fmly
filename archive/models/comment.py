from django.db import models
from .image import Image
from django.urls import reverse

from cmnsd.models.cmnsd_basemodel import BaseModel
  
class Comment(BaseModel):
  # Content
  content             = models.TextField(help_text='Markdown supported')
  image               = models.ForeignKey(Image, related_name='comments', on_delete=models.CASCADE)
  
  class Meta:
    ''' Unique together
        Any comment to an image should be unique for that image and user,
        disallowing double comments.
    '''
    unique_together = ('user', 'image', 'content')
    ordering = ['-date_created']

  def __str__(self):
    deleted = ' (deleted)' if self.status == 'x' else ''
    return self.user.username + ' on ' + self.image.title + deleted
  
  def get_absolute_url(self):
    return reverse('archive:image', kwargs={'slug': self.image.slug})