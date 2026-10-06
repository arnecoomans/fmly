import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class ThumbnailCropTests(TestCase):
  """An item's own thumbnail crop (Content.thumb_crop_*, ContentThumbnailForm):
  a 4:3 box, set in a dialog on its page; the cards and small thumbnails
  use it, the large view doesn't; a new crop is a new address."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.editor = get_user_model().objects.create(username='editor')
    self.editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    # Left half red, right half blue: which half a thumbnail shows says where it was cut.
    image = Image.new('RGB', (800, 300), 'red')
    image.paste((0, 0, 255), (400, 0, 800, 300))
    buffer = io.BytesIO()
    image.save(buffer, 'JPEG')
    self.item = Content.objects.create(name='Strook', kind='photo', user=self.editor, status='p', visibility='c')
    self.item.file.save('strook.jpg', ContentFile(buffer.getvalue()))

  def save_crop(self, **fields):
    self.item.refresh_from_db()
    data = {'_modified': self.item.date_modified.isoformat(), **{f'thumbnail-{k}': v for k, v in fields.items()}}
    return self.client.post(f'/api/content/{self.item.token}/form/thumbnail/', data)

  def thumb(self, preset, client=None):
    response = (client or self.client).get(f'/content/{self.item.token}/thumb/{preset}/')
    self.assertEqual(response.status_code, 200)
    return Image.open(io.BytesIO(b''.join(response.streaming_content if response.streaming else [response.content]))).convert('RGB')

  def test_the_card_follows_the_crop(self):
    self.assertEqual(self.save_crop(thumb_crop_x='0.6', thumb_crop_y='0', thumb_crop_w='0.4', thumb_crop_h='1').status_code, 200)
    self.item.refresh_from_db()
    self.assertEqual(self.item.thumb_crop_box, (0.6, 0.0, 0.4, 1.0))
    card = self.thumb('card')
    self.assertGreater(card.getpixel((card.width // 2, card.height // 2))[2], 200)   # blue: the right part
    avatar = self.thumb('avatar')
    self.assertGreater(avatar.getpixel((avatar.width // 2, avatar.height // 2))[2], 200)
    large = self.thumb('large')
    self.assertEqual(large.size, (800, 300))                                          # the large view: the whole image

  def test_turned_card_keeps_its_shape(self):
    self.save_crop(thumb_crop_x='0', thumb_crop_y='0', thumb_crop_w='1', thumb_crop_h='1', thumb_rotation='90')
    card = self.thumb('card')
    self.assertGreater(card.width, card.height)                                       # still a landscape card

  def test_address_changes_with_the_crop_and_reset(self):
    from content.templatetags.content_tags import thumb_url
    plain = thumb_url(self.item, 'card')
    self.assertNotIn('?v=', plain)
    self.save_crop(thumb_crop_x='0.1', thumb_crop_y='0', thumb_crop_w='0.5', thumb_crop_h='1')
    self.item.refresh_from_db()
    cropped = thumb_url(self.item, 'card')
    self.assertIn('?v=', cropped)
    self.save_crop(thumb_crop_x='0.1', thumb_crop_y='0', thumb_crop_w='0.5', thumb_crop_h='1', reset='1')
    self.item.refresh_from_db()
    self.assertIsNone(self.item.thumb_crop_box)                                       # automatic again
    self.assertEqual(thumb_url(self.item, 'card'), plain)

  def test_outside_the_image_is_refused(self):
    self.assertEqual(self.save_crop(thumb_crop_x='0.8', thumb_crop_y='0', thumb_crop_w='0.5', thumb_crop_h='1').status_code, 400)

  def test_the_block_in_edit_mode(self):
    html = self.client.get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-edit-name=thumbnail', html)
    form = self.client.get(f'/api/content/{self.item.token}/form/thumbnail/').json()['html'].replace('"', '')
    self.assertIn('thumb-crop__frame', form)
    self.assertIn('data-crop=w', form)
