from django.db import models
from django.urls import reverse, reverse_lazy
from django.contrib.auth.models import User
from .image import Image


class Comment(models.Model):
  # Meta
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
  # Content
  content             = models.TextField(help_text='Markdown supported')
  image               = models.ForeignKey(Image, related_name='comments', on_delete=models.CASCADE)
  
  def __str__(self):
    return self.user.username + ' on ' + self.image.title
  
  def save(self, *args, **kwargs):
    if not self.user:
      self.user = request.user
    return super(Comment, self).save(*args, **kwargs)

  def get_absolute_url(self):
    return "/object/%i/" % self.image.id