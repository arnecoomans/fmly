from django.db import models
from django.urls import reverse_lazy
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User

class Tag(models.Model):
  title               = models.CharField(max_length=255)
  slug                = models.SlugField(unique=True)
  description         = models.TextField(blank=True, help_text='Write down why this tag is relevant. Plain text only.')
  
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  date_modified       = models.DateTimeField(auto_now=True)
  date_created        = models.DateTimeField(auto_now_add=True)
  
  def __str__(self):
    return self.title
  
  class Meta:
        ordering = (['title'])
  
  # Save all tags as lowercase. Use |title in the template for displaying  
  def save(self, *args, **kwargs):
    self.title = self.title.lower()
    self.slug = slugify(self.title)
    return super(Tag, self).save(*args, **kwargs)

  def get_absolute_url(self):
    return reverse_lazy('archive:tags')
  
  def get_images(self):
    return self.images.all().filter(is_deleted=False, visibility_frontpage=True)
  def get_hidden_images(self):
    return self.images.all().filter(is_deleted=False, visibility_frontpage=False)