from django.test import TestCase
from .setup import setUp

from archive.models.comment import Comment
from archive.models.image import Image
from django.contrib.auth.models import User

class ImageTestCase(setUp, TestCase):

  def setUp(self):
    super().setUp()
    
  def test_image_has_title(self):
    image = Image.objects.get(slug='test-image-one')
    self.assertEqual(image.title, 'This is a test-image')
  
  def test_image_has_tag(self):
    image = Image.objects.get(slug='test-image-one')
    self.assertEqual(image.count_tags(), 2)
