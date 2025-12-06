from django.db import models
from cmnsd.models.Category import Category

from .BaseIcon import BaseIcon
''' Category model
'''
class Category(Category, BaseIcon):
  """ Extends CMNSD.models:Category with archive-specific fields
  """
  pass