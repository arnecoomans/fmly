from django.db import models
from django.urls import reverse, reverse_lazy
from django.contrib.auth.models import User
from .tag import Tag
from .person import Person

# Create Thumbnail function
def get_thumbnail(image):
  # Check if suffix is supported.
  if image.name[-4:].lower() not in ['.jpg', '.png'] and image.name[-5:].lower() not in ['.jpeg',]:
    # There is an image ready that reads Format Not Supported. This is a
    # friendly way to inform the user of the error.
    return 'documents/format_not_supported.jpg'
  import base64
  from io import BytesIO
  from PIL import Image, ImageOps
  Image.MAX_IMAGE_PIXELS = 933120000

  thumbnail_size = 150, 300
  data_img = BytesIO()
  tiny_img = Image.open(image)
  tiny_img = ImageOps.exif_transpose(tiny_img)
  tiny_img.thumbnail(thumbnail_size)
  tiny_img.save(data_img, format="BMP")
  tiny_img.close()
  try:
      return "data:image/jpg;base64,{}".format(
          base64.b64encode(data_img.getvalue()).decode("utf-8")
      )
  except UnicodeDecodeError:
    # There is an image ready that reads Decode Error. This is a
    # friendly way to inform the user.
    return 'documents/decode_error.jpg'

class Group(models.Model):
  title               = models.CharField(max_length=255, blank=True)
  description         = models.CharField(max_length=512, blank=True, null=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  tag                 = models.ManyToManyField(Tag, blank=True, related_name='groups')
  def __str__(self):
    title = self.title
    if self.description:
      title += ' (' + self.description[:32]
      if len(self.description) > 32:
        title += '...'
      self.title += ')'
    return title

class Attachment(models.Model):
  file                = models.FileField(null=True, blank=True, upload_to='files', help_text='Possible to attach file to an image. Use for pdf, doc, excel, etc.')
  desciption          = models.CharField(max_length=512, blank=True, null=True)
  # Meta
  uploaded_at         = models.DateTimeField(auto_now_add=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  def __str__(self) -> str:
    return self.desciption

class Image(models.Model):
  # Document details
  source              = models.ImageField()
  thumbnail           = models.CharField(max_length=2000, blank=True, null=True)
  title               = models.CharField(max_length=255)
  description         = models.TextField(blank=True, help_text='Markdown supported')
  document_source     = models.CharField(max_length=255, blank=True, help_text='Link or textual description of source')
  # Relations
  people              = models.ManyToManyField(Person, blank=True, related_name='images', help_text='Tag people that are on the photo')
  tag                 = models.ManyToManyField(Tag, blank=True, related_name='images')
  attachment          = models.FileField(null=True, blank=True, upload_to='files', help_text='Possible to attach file to an image. Use for pdf, doc, excel, etc.')
  attachments         = models.ManyToManyField(Attachment, blank=True, related_name='images')
  is_portrait_of      = models.OneToOneField(Person, on_delete=models.CASCADE, related_name='portrait', blank=True, null=True)
  in_group            = models.ManyToManyField(Group, blank=True, related_name='images', help_text='Group images')
  # Dating
  year                = models.PositiveSmallIntegerField(blank=True, null=True, help_text='Is automatically filled when date is supplied')
  date                = models.DateField(null=True, blank=True, help_text='Format: year-month-date, for example 1981-08-11')
  # Meta
  uploaded_at         = models.DateTimeField(auto_now_add=True)
  user                = models.ForeignKey(User, on_delete=models.CASCADE)
  show_in_index       = models.BooleanField(default=True)
  is_deleted          = models.BooleanField(default=False)

  def __str__(self):
    return self.get_indexed_name()
    
  def get_indexed_name(self):
    title = self.title if self.title != '' else '--no title--'
    id = str(self.id)
    while len(id) < 4:
      id = '0' + id
    if self.is_deleted:
      title += ' (deleted)'
    return id + ' ' + title
  
  def count_tags(self):
    return self.tag.count()
  def count_people(self):
    return self.people.count()
  def has_thumbnail(self):
    return True if self.thumbnail else False
  def get_year(self):
    return self.date.year if self.date else self.year
  # def get_attachment_type(self):
  #   if not self.attachment:
  #     return None
  #   elif self.attachment.name[-4:].lower() == '.pdf':
  #     return 'pdf'
  #   elif self.attachment.name[-4:].lower() == '.doc' or self.attachment.name[-5:].lower() == '.docx':
  #     return 'word'
  #   elif self.attachment.name[-4:].lower() == '.xls' or self.attachment.name[-5:].lower() == '.xlsx':
  #     return 'excel'
  #   elif self.attachment.name[-4:].lower() == '.jpg' or self.attachment.name[-5:].lower() == '.jpeg':
  #     return 'jpeg'
  #   elif self.attachment.name[-4:].lower() == '.png':
  #     return 'png'
  #   elif self.attachment.name[-4:].lower() == '.txt':
  #     return 'txt'
  #   elif self.attachment.name[-4:].lower() == '.csv':
  #     return 'csv'
  #   else:
  #     return 'unknown'

  def get_absolute_url(self):
    return reverse('archive:image', kwargs={'pk': self.pk, 'name': self.title })  

  def save(self, *args, **kwargs):
    # Enforce user
    if not self.user:
      self.user = request.user
    # Fill in year if date is known
    if not self.year and self.date:
      self.year = int(self.date.year)
    # Generate thumbnail
    if self.source and not self.thumbnail:
      self.thumbnail = get_thumbnail(self.source)
    # Save
    return super(Image, self).save(*args, **kwargs)