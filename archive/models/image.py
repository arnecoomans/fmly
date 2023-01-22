from django.db import models
from django.urls import reverse
from django.contrib.auth.models import User
from django.conf import settings
from .tag import Tag
from .person import Person
from PIL import Image
from pathlib import Path
from django.core.validators import MaxValueValidator, MinValueValidator
from django.template.defaultfilters import slugify

# Create Thumbnail function
def get_thumbnail(image):
  # Check if suffix is supported.
  if image.name[-4:].lower() not in ['.jpg', '.png'] and \
     image.name[-5:].lower() not in ['.jpeg',]:
    # There is an image ready that reads Format Not Supported. This is a
    # friendly way to inform the user of the error.
    return 'documents/format_not_supported.jpg'
  #from PIL import Image
  import PIL
  PIL.Image.MAX_IMAGE_PIXELS = 933120000

  tgt_width = 300
  tgt_file = 'thumbnails/' + str(image.name)
  try:
    with PIL.Image.open(image.path) as img:
      width, height = img.size
      ratio = width / height
      tgt_height = int(tgt_width / ratio)
      img = img.resize((tgt_width, tgt_height), PIL.Image.ANTIALIAS)
      img.save(settings.MEDIA_ROOT.joinpath(tgt_file))
      return tgt_file
  except:
    return None

class Group(models.Model):
  title               = models.CharField(max_length=255, blank=True)
  description         = models.CharField(max_length=512, blank=True, null=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  tag                 = models.ManyToManyField(Tag, blank=True, related_name='groups')
  
  def __str__(self):
    title = self.title
    ''' Prepend title with tag if there is one tag set. 
        If more tags are set, it would get too messy. 
    '''
    if self.tag and self.tag.all().count() == 1:
      for tag in self.tag.all():
        title = f"{ tag }: { title }"
    ''' Append title with short description if set 
    '''
    if self.description:
      title += ' (' + self.description[:32]
      if len(self.description) > 32:
        title += '...'
      self.title += ')'
    return title

  def count_images(self):
    return self.images.filter(is_deleted=False).count()

class Attachment(models.Model):
  slug                = models.CharField(max_length=255, unique=True)
  file                = models.FileField(null=True, upload_to='files', help_text='Possible to attach file to an image. Use for pdf, doc, excel, etc.')
  description         = models.CharField(max_length=512, blank=True, null=True)
  # Meta
  size                = models.IntegerField(default=0)
  uploaded_at         = models.DateTimeField(auto_now_add=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  is_deleted          = models.BooleanField(default=False)

  def __str__(self) -> str:
    description = str(self.description)
    if len(description) < 1:
      description = self.slug
    if self.is_deleted:
      description = f"[Deleted] { description }"
    return str(description)
    
  def get_absolute_url(self):
      return reverse("archive:attachment", kwargs={"slug": self.slug})
  
  
  def extension(self):
    return Path(str(self.file)).suffix[1:].lower()

  def storeSize(self):
    from os import stat
    file_stats = stat(settings.MEDIA_ROOT.joinpath(str(self.file  )))
    self.size = file_stats.st_size
    self.save()

  ''' Display Image File size. Calculate if not stored yet '''
  def getSize(self):
    ''' https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python '''
    from math import floor, pow, log
    if self.size == 0:
      self.storeSize()
    if self.size == 0:
      return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(floor(log(self.size, 1024)))
    p = pow(1024, i)
    s = round(self.size / p, 2)
    return "%s %s" % (s, size_name[i])

''' Use default random value when migrating to slug '''
import random
def random_string():
  return str(random.randint(10000, 99999))

class Image(models.Model):
  # Document details
  slug                = models.CharField(max_length=255, unique=True, default=random_string)
  source              = models.ImageField(height_field='height', width_field='width')
  thumbnail           = models.CharField(max_length=2000, blank=True, null=True)
  title               = models.CharField(max_length=255, blank=True)
  description         = models.TextField(blank=True, help_text='Markdown supported')
  document_source     = models.CharField(max_length=255, blank=True, help_text='Link or textual description of source')
  # Relations
  people              = models.ManyToManyField(Person, blank=True, related_name='images', help_text='Tag people that are on the photo')
  tag                 = models.ManyToManyField(Tag, blank=True, related_name='images')
  attachments         = models.ManyToManyField(Attachment, blank=True, related_name='images')
  is_portrait_of      = models.OneToOneField(Person, on_delete=models.CASCADE, related_name='portrait', blank=True, null=True)
  in_group            = models.ManyToManyField(Group, blank=True, related_name='images', help_text='Group images')
  # Dating
  MONTHS = [(1, 'januari'), (2, 'februari'), (3, 'maart'), (4, 'april'), (5, 'mei'), (6, 'juni'), (7, 'juli'), (8, 'augustus'), (9, 'september'), (10, 'oktober'), (11, 'november'), (12, 'december')]
  year                = models.PositiveSmallIntegerField(blank=True, null=True, help_text='')
  month               = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', choices=MONTHS)
  day                 = models.PositiveSmallIntegerField(blank=True, null=True, help_text='', validators=[MaxValueValidator(31), MinValueValidator(1)])
  # Meta
  size                = models.IntegerField(default=0)
  width               = models.IntegerField(default=0)
  height              = models.IntegerField(default=0)
  # ORIENTATION_CHOICES = [('p', 'portrait'), ('l', 'landscape'), ('s', 'square'), ('u', 'unknown')]
  # orientation         = models.CharField(max_length=1, choices=ORIENTATION_CHOICES, default='u')
  
  uploaded_at         = models.DateTimeField(auto_now_add=True)
  date_modified       = models.DateTimeField(auto_now=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  show_in_index       = models.BooleanField(default=True)
  is_deleted          = models.BooleanField(default=False)

  def __str__(self):
    return self.get_indexed_name()
  
  ''' Get Save Slug
      Loop through existing slugs and append slug with counter if Unique contraint would fail
  '''
  def get_safe_slug(self, title, is_deleted):
    slug = slugify(title).lower()
    if is_deleted:
      slug = f"[deleted]_{slug}"
    images = Image.objects.all().values_list('slug')
    if images.filter(slug=slug).count() > 0:
      i = 1
      while images.filter(slug=f"{slug}{str(i)}").count() > 0:
        i += 1
      slug = f"{slug}{str(i)}"
    return slug

  def get_indexed_name(self):
    title = self.title if self.title != '' else '--no title--'
    id = str(self.id)
    while len(id) < 4:
      id = '0' + id
    if self.is_deleted:
      title += ' (deleted)'
    return id + ' ' + title
  
  ''' Related Object Methods'''
  def count_comments(self):
    return self.comments.filter(is_deleted=False).count()
  def get_comments(self):
    return self.comments.filter(is_deleted=False)
  def count_attachments(self):
    return self.attachments.filter(is_deleted=False).count()
  def get_attachments(self):
    return self.attachments.filter(is_deleted=False)
  def get_groups(self):
    groups = {}
    for group in self.in_group.all():
      if group.images.exclude(is_deleted=True).count() > 1:
        groups[group.title] = group.images.exclude(is_deleted=True).count()
    return groups
  def get_grouped_images(self):
    groups = {}
    for group in self.in_group.all():
      groups[group.title] = group.images.exclude(is_deleted=True).exclude(id=self.id)
    return groups

  def count_tags(self):
    return self.tag.count()
  def count_people(self):
    return self.people.count()
  def has_thumbnail(self):
    return True if self.thumbnail else False
  def extension(self):
    return Path(str(self.source)).suffix[1:].lower()
  
  
  def get_absolute_url(self):
    return reverse('archive:image', kwargs={'slug': self.title })  

  ''' Cache Metadata 
      Image Metadata is sometimes displayed as nice-to-have. To minimize file system calls, this information is cached in the database.
  '''
  ''' Store Image File Size '''
  def storeSize(self):
    from os import stat
    file_stats = stat(settings.MEDIA_ROOT.joinpath(str(self.source)))
    self.size = file_stats.st_size
    self.save()

  ''' Display Image File size. Calculate if not stored yet '''
  def getSize(self):
    ''' https://stackoverflow.com/questions/5194057/better-way-to-convert-file-sizes-in-python '''
    from math import floor, pow, log
    if self.size == 0:
      self.storeSize()
    if self.size == 0:
      return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(floor(log(self.size, 1024)))
    p = pow(1024, i)
    s = round(self.size / p, 2)
    return "%s %s" % (s, size_name[i])

  def save(self, *args, **kwargs):
    # Enforce user
    ''' If no title is given, use source file name as title '''
    if not self.title:
      self.title = str(self.source.name.replace('_', ' '))
    ''' If no slug is given, base slug off title '''
    if not self.slug:
      self.slug = self.get_safe_slug(self.title, self.is_deleted)
    if self.is_deleted and self.slug[:10] != '[deleted]_':
      self.slug = '[deleted]_'+ self.title
    ''' Generate thumbnail '''
    if self.source and not self.thumbnail:
      self.thumbnail = get_thumbnail(self.source)
    ''' Save '''
    return super(Image, self).save(*args, **kwargs)