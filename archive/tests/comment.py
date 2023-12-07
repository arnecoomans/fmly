from django.test import TestCase
from .setup import setUp

from archive.models.comment import Comment
from archive.models.image import Image
from django.contrib.auth.models import User

class CommentTestCase(setUp, TestCase):

  def setUp(self):
    super().setUp()
    
  def test_image_has_one_comment(self):
    image = Image.objects.get(slug='test-image-one')
    self.assertEqual(image.count_comments(), 1)
  
  
