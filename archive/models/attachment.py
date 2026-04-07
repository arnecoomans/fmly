from pathlib import Path
from django.db import models
from django.urls import reverse
from django.conf import settings

from cmnsd.models import BaseModel


class Attachment(BaseModel):
  slug                = models.CharField(max_length=255, unique=True)
  file                = models.FileField(null=True, upload_to='files', help_text='Possible to attach file to an image. Use for pdf, doc, excel, etc.')
  description         = models.CharField(max_length=512, blank=True, null=True)
  # Meta
  size                = models.IntegerField(default=0)
  is_deleted          = models.BooleanField(default=False)

  def __str__(self) -> str:
    description = str(self.description)
    if len(description) < 1:
      description = self.slug
    return str(description)

  def get_absolute_url(self):
    return reverse("archive:attachment", kwargs={"slug": self.slug})

  def filename(self):
    return Path(str(self.file)).name

  def extension(self):
    return Path(str(self.file)).suffix[1:].lower()

  def storeSize(self):
    from os import stat
    file_stats = stat(settings.MEDIA_ROOT.joinpath(str(self.file)))
    self.size = file_stats.st_size
    self.save()

  def getSize(self):
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
