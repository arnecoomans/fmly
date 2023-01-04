from django.db import models
from django.contrib.auth.models import User

from .person import Person

class Tree(models.Model):
  title               = models.CharField(max_length=255, blank=True, help_text='Optional title')
  image               = models.ImageField()
  scope               = models.JSONField()
  # Family Tree Meta data
  people              = models.ManyToManyField(Person, blank=True, related_name='trees', help_text='People referenced in family tree')
  # Object meta data
  date_created        = models.DateTimeField(auto_now_add=True)
  date_modified       = models.DateTimeField(auto_now=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  is_deleted          = models.BooleanField(default=False)