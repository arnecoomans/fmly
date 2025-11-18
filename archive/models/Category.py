from django.db import models
from cmnsd.models.Category import Category

''' Category model
'''
class Category(Category):
  """ Extends CMNSD.models:Category with archive-specific fields
  """
  icon = models.CharField(max_length=32, blank=True, help_text='bootstrap icon name, e.g. "camera" for category icons')

  def get_icon_file(self):
    if self.icon:
      return f'img/bootstrap-icons/{self.icon}.svg'
    return 'img/bootstrap-icons/list.svg'