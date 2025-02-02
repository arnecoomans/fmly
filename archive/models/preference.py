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

  allow_read_attribute = 'Self'  # Allow authenticated users to read attributes via JSON requests
  allow_suggest_attribute = 'Self'  # Allow authenticated users to suggest attributes via JSON requests
  allow_set_attribute = 'Self'  # Allow staff users to set attributes via JSON requests
  allow_create_attribute = False # Disallow creating new objects via JSON requests by setting to False
  
  def __str__(self):
    return f"Voorkeuren van { self.user }"
  
