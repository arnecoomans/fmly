from django.db import models
from django.contrib.auth.models import User
from .image import Image

class Preference(models.Model):
  user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preference')
  ''' Display preferences '''
  show_hidden_files   = models.BooleanField(default=False)
  ''' Upload preferences '''
  show_new_uploads    = models.BooleanField(default=True)

  ''' Favorites '''
  favorites           = models.ManyToManyField(Image, blank=True, related_name="loved_by")

  def __str__(self):
    return f"Voorkeuren van { self.user }"
  
