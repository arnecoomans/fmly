from django.db import models
from django.urls import reverse_lazy
from django.template.defaultfilters import slugify

class Tag(models.Model):
  title               = models.CharField(max_length=255)
  slug                = models.SlugField(unique=True)
  description         = models.TextField(blank=True, help_text='Write down why this tag is relevant. Plain text only.')

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
    return reverse_lazy('archive:tag', kwargs={'slug': self.slug})