from django.db import models
from django.contrib.auth.models import User

#from .attendeeoptions import AttendeeOptions

class Event(models.Model):
  slug                = models.CharField(max_length=255, unique=True)
  title               = models.CharField(max_length=255)
  description         = models.TextField(blank=True, help_text='Markdown supported')
  location            = models.CharField(max_length=255)
  location_url        = models.CharField(max_length=255)
  
  date_created        = models.DateTimeField(auto_now_add=True)
  date_modified       = models.DateTimeField(auto_now=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  is_deleted          = models.BooleanField(default=False)

  def __str__(self) -> str:
    return self.title
  