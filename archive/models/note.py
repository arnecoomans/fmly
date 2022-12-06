from django.db import models
from django.urls import reverse, reverse_lazy

from django.contrib.auth.models import User
from .person import Person
from .tag import Tag

#from django.template.defaultfilters import slugify

class Note(models.Model):
  title               = models.CharField(max_length=255, blank=True)
  content             = models.TextField(blank=True, help_text='Markdown Supported')
  # Meta
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  # Relations
  people              = models.ManyToManyField(Person, blank=True, related_name='notes')
  tag                 = models.ManyToManyField(Tag, blank=True, related_name='notes')
  
  def __str__(self):
    return self.title
  def get_absolute_url(self):
        return reverse('archive:note', kwargs={'pk': self.pk})
