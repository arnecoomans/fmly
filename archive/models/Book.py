from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils.text import slugify

from .tag import Tag
from .person import Person
from .attachment import Attachment

from cmnsd.models import BaseModel

class Book(BaseModel):
  title = models.CharField(max_length=255)
  author = models.CharField(max_length=255, blank=True)
  year = models.PositiveIntegerField(null=True, blank=True)
  publisher = models.CharField(max_length=255, blank=True)
  isbn = models.CharField(max_length=20, blank=True)
  description = models.TextField(blank=True)
  tags = models.ManyToManyField(Tag, blank=True)
  people = models.ManyToManyField(Person, blank=True, related_name='books')
  cover = models.ImageField(upload_to='books/covers/', blank=True)
  attachments = models.ManyToManyField(Attachment, blank=True, related_name='books')

  def __str__(self):
    return self.title

  def get_absolute_url(self):
    return reverse('archive:book-detail', kwargs={'pk': self.pk})
  def read_count(self):
    return self.collection_items.filter(read=True).count()


class Collection(models.Model):
  user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='collections')
  people = models.ManyToManyField(Person, blank=True, related_name='collections')
  name = models.CharField(max_length=255)  # "Grandpa's shelf", "My ebooks"
  slug = models.SlugField(max_length=255, unique=True)
  description = models.TextField(blank=True)
  tags = models.ManyToManyField(Tag, blank=True)

  def __str__(self):
    return self.name

  def get_absolute_url(self):
    return reverse('archive:book-collection-detail', kwargs={'slug': self.slug})

  def save(self, *args, **kwargs):
    if not self.slug:
      self.slug = slugify(self.name)
    super().save(*args, **kwargs)

  def book_count(self):
    return self.items.count() 


class CollectionItem(models.Model):
  collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='items')
  book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='collection_items')
  read = models.BooleanField(default=False)
  notes = models.TextField(blank=True)
  tags = models.ManyToManyField(Tag, blank=True)  # status: wishlist/owned, format: physical/ebook/audiobook

  class Meta:
    constraints = [models.UniqueConstraint(fields=['collection', 'book'], name='unique_collection_book')]

  def __str__(self):
    return f"{self.collection.name} - {self.book.title}"

  def get_absolute_url(self):
    return self.collection.get_absolute_url()