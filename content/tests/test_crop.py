import io

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from PIL import Image

from content.crop import stored_rectangle
from content.models import Content, Portrait
from people.models import Person

from .test_models import MEDIA, ContentTestCase
from .test_views import body


class StoredRectangleTests(SimpleTestCase):
  def test_upright_is_unchanged(self):
    self.assertEqual(stored_rectangle((0.1, 0.2, 0.3, 0.4), 1), (0.1, 0.2, 0.4, 0.6000000000000001))

  def test_rotated_90_clockwise(self):
    # Orientation 6: the stored image is turned counter-clockwise, so the
    # displayed top half is the stored left half.
    self.assertEqual(stored_rectangle((0, 0, 1, 0.5), 6), (0, 0, 0.5, 1))

  def test_rotated_180(self):
    self.assertEqual(stored_rectangle((0, 0, 0.5, 0.5), 3), (0.5, 0.5, 1, 1))


def two_color_jpeg(orientation=1):
  """200x100 as stored: left half red, right half blue."""
  image = Image.new('RGB', (200, 100), 'blue')
  image.paste((255, 0, 0), (0, 0, 100, 100))
  exif = Image.Exif()
  exif[0x0112] = orientation
  buffer = io.BytesIO()
  image.save(buffer, 'JPEG', exif=exif, quality=95)
  return buffer.getvalue()


def center_color(response):
  image = Image.open(io.BytesIO(body(response))).convert('RGB')
  r, g, b = image.getpixel((image.width // 2, image.height // 2))
  return 'red' if r > b else 'blue'


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class PortraitCropViewTests(ContentTestCase):
  def setUp(self):
    super().setUp()
    self.member = get_user_model().objects.create(username='member')
    self.alice = Person.objects.create(given_name='Alice', user=self.user, status='p', visibility='c')
    self.bob = Person.objects.create(given_name='Bob', user=self.user, status='p', visibility='c')

  def photo(self, orientation=1, visibility='c'):
    content = Content(user=self.user, name='Group photo', kind=Content.Kind.PHOTO, status='p', visibility=visibility)
    content.file = ContentFile(two_color_jpeg(orientation), name='IMG_1.jpg')
    content.save()
    return content

  def get(self, content, person):
    self.client.force_login(self.member)
    return self.client.get(reverse('content:portrait', args=[content.token, person.token]))

  def test_group_photo_cropped_per_person(self):
    photo = self.photo()
    Portrait.objects.create(person=self.alice, content=photo, crop_x=0, crop_y=0, crop_w=0.5, crop_h=1)
    Portrait.objects.create(person=self.bob, content=photo, crop_x=0.5, crop_y=0, crop_w=0.5, crop_h=1)
    self.assertEqual(center_color(self.get(photo, self.alice)), 'red')
    self.assertEqual(center_color(self.get(photo, self.bob)), 'blue')

  def test_crop_follows_exif_rotation(self):
    # Orientation 6 displays the stored left (red) half at the top.
    photo = self.photo(orientation=6)
    Portrait.objects.create(person=self.alice, content=photo, crop_x=0, crop_y=0, crop_w=1, crop_h=0.5)
    Portrait.objects.create(person=self.bob, content=photo, crop_x=0, crop_y=0.5, crop_w=1, crop_h=0.5)
    self.assertEqual(center_color(self.get(photo, self.alice)), 'red')
    self.assertEqual(center_color(self.get(photo, self.bob)), 'blue')

  def test_size_is_avatar_preset(self):
    photo = self.photo()
    Portrait.objects.create(person=self.alice, content=photo, crop_x=0, crop_y=0, crop_w=0.5, crop_h=1)
    self.assertEqual(Image.open(io.BytesIO(body(self.get(photo, self.alice)))).size, (160, 160))

  def test_access(self):
    photo = self.photo()
    Portrait.objects.create(person=self.alice, content=photo)
    url = reverse('content:portrait', args=[photo.token, self.alice.token])
    self.assertEqual(self.client.get(url).status_code, 404)  # anonymous: community photo and person
    self.assertEqual(self.get(photo, self.bob).status_code, 404)  # not Bob's portrait
    Person.objects.filter(pk=self.alice.pk).update(status='x')
    self.assertEqual(self.get(photo, self.alice).status_code, 404)  # deleted person

  def test_version_changes_with_crop(self):
    link = Portrait(person=self.alice, content=self.photo())
    self.assertEqual(link.version, 'full')
    link.crop_x, link.crop_y, link.crop_w, link.crop_h = 0.1, 0.1, 0.5, 0.5
    self.assertNotEqual(link.version, 'full')
