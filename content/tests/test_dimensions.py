import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content
from content.templatetags.content_tags import file_info

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class DimensionTests(TestCase):
  """An image's width and height as shown (Content.measure), and the file
  line on its page (content_tags.file_info)."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = get_user_model().objects.create(username='a')
    self.user.save()

  def save_image(self, size, orientation=None):
    buffer = io.BytesIO()
    image = Image.new('RGB', size, 'white')
    exif = Image.Exif()
    if orientation:
      exif[0x0112] = orientation
    image.save(buffer, 'JPEG', exif=exif)
    item = Content(name='Foto', kind='photo', user=self.user, status='p', visibility='c')
    item.file = ContentFile(buffer.getvalue(), name='foto.jpg')
    item.save()
    item.refresh_from_db()
    return item

  def test_measured_on_save(self):
    item = self.save_image((400, 300))
    self.assertEqual((item.width, item.height), (400, 300))

  def test_turned_by_exif(self):
    item = self.save_image((400, 300), orientation=6)          # stored sideways, shown upright
    self.assertEqual((item.width, item.height), (300, 400))

  def test_file_line(self):
    item = self.save_image((400, 300))
    self.assertTrue(file_info(item).startswith('JPEG · 400 × 300 px · '))
    client = Client()
    client.force_login(self.user)
    self.assertContains(client.get(item.get_absolute_url()), '400 × 300 px')

  def test_not_an_image(self):
    item = Content(name='Brief', kind='document', user=self.user, status='p', visibility='c')
    item.file = ContentFile(b'%PDF-1.4', name='brief.pdf')
    item.save()
    item.refresh_from_db()
    self.assertIsNone(item.width)
    self.assertTrue(file_info(item).startswith('PDF · '))

  def test_heic(self):
    # An iPhone photo dropped from a computer: dimensions, a JPEG thumbnail,
    # and the lightbox zooms into a JPEG rendering, not the HEIC file.
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(buffer, 'HEIF')
    item = Content(name='Telefoonfoto', kind='photo', user=self.user, status='p', visibility='c')
    item.file = ContentFile(buffer.getvalue(), name='IMG_0001.heic')
    item.save()
    item.refresh_from_db()
    self.assertEqual((item.width, item.height), (40, 30))
    client = Client()
    client.force_login(self.user)
    response = client.get(f'/content/{item.token}/thumb/card/')
    self.assertEqual(response.status_code, 200)
    data = b''.join(response.streaming_content) if response.streaming else response.content
    self.assertEqual(Image.open(io.BytesIO(data)).format, 'JPEG')
    self.assertTrue(item.zoom_url().endswith('/thumb/xlarge/'))


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class UnnamedAddressTests(TestCase):
  """An item without a name yet: /content/<token>/, not the token twice;
  named, the slug follows."""

  def test_address(self):
    user = get_user_model().objects.create(username='a')
    user.save()
    item = Content.objects.create(kind='photo', user=user, status='p', visibility='c', original_filename='IMG_1234.jpg')
    self.assertEqual(item.get_absolute_url(), f'/content/{item.token}/')
    client = Client()
    client.force_login(user)
    self.assertEqual(client.get(f'/content/{item.token}/').status_code, 200)
    self.assertEqual(client.get(f'/content/{item.token}/{item.slug}/').url, f'/content/{item.token}/')   # the long form redirects
    item.name = 'Het Indonesië van nu'
    item.save()
    self.assertEqual(item.get_absolute_url(), f'/content/{item.token}/het-indonesie-van-nu/')

  def test_the_redirect_keeps_the_query(self):
    user = get_user_model().objects.create(username='b')
    user.save()
    item = Content.objects.create(name='Feest', kind='photo', user=user, status='p', visibility='c')
    client = Client()
    client.force_login(user)
    self.assertEqual(client.get(f'/content/{item.token}/?open=thumbnail').url, f'{item.get_absolute_url()}?open=thumbnail')
