from django.db import models
from django.contrib.auth.models import User

class Preference(models.Model):
  user                = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preference')
  ''' Display preferences '''
  show_hidden_files   = models.BooleanField(default=False)
  ''' Upload preferences '''
  show_new_uploads    = models.BooleanField(default=True)

  def __str__(self):
    return f"Voorkeuren van { self.user }"
  
