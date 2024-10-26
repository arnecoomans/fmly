from django.db import models
from django.contrib.auth.models import User
from .image import Image
from django.urls import reverse


class Comment(models.Model):
  # Meta
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  is_deleted          = models.BooleanField(default=False)
  user                = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
  # Content
  content             = models.TextField(help_text='Markdown supported')
  image               = models.ForeignKey(Image, related_name='comments', on_delete=models.CASCADE)
  
  class Meta:
    ''' Unique together
        Any comment to an image should be unique for that image and user,
        disallowing double comments.
    '''
    unique_together = ('user', 'image', 'content')

  def __str__(self):
    deleted = ' (deleted)' if self.is_deleted else ''
    return self.user.username + ' on ' + self.image.title + deleted
  
  def get_absolute_url(self):
    return reverse('archive:image', kwargs={'slug': self.image.slug})