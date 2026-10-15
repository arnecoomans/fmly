import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content
from content.previews import ensure_preview, preview_name

MEDIA = tempfile.mkdtemp()


def pdf(color='red', size=(300, 400)):
  """A real one-page PDF (Pillow writes them), the page one colour."""
  buffer = io.BytesIO()
  Image.new('RGB', size, color).save(buffer, 'PDF')
  return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class PdfPreviewTests(TestCase):
  """A PDF's first page as its preview (content/previews.py): thumbnails in
  every size, an image card in the lists - derived, never entered by hand."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = get_user_model().objects.create(username='viewer')
    self.user.user_permissions.add(Permission.objects.get(codename='add_content'))
    self.user.save()
    self.client = Client()
    self.client.force_login(self.user)

  def item(self, data=None, name='passagierslijst.pdf', checksum='a' * 64):
    item = Content.objects.create(name='Passagierslijst', kind='document', user=self.user, status='p', visibility='c', checksum=checksum)
    item.file.save(name, ContentFile(data or pdf()), save=True)
    return item

  def test_first_page_rendered_once(self):
    item = self.item()
    name = ensure_preview(item)
    self.assertEqual(name, preview_name(item))
    with default_storage.open(name) as file, Image.open(file) as image:
      self.assertEqual(max(image.size), 1600)               # PREVIEW_SIZE, the longer side
      self.assertGreater(image.getpixel((100, 100))[0], 200)  # the red page
    self.assertEqual(ensure_preview(item), name)              # kept, not rendered again

  def test_thumbnails_in_every_size(self):
    item = self.item()
    self.assertTrue(item.has_thumbnail)
    for preset in ('card', 'avatar', 'large'):
      self.assertEqual(self.client.get(f'/content/{item.token}/thumb/{preset}/').status_code, 200, preset)

  def test_a_new_file_gets_a_new_preview(self):
    item = self.item()
    first = preview_name(item)
    item.checksum = 'b' * 64
    self.assertNotEqual(preview_name(item), first)

  def test_unreadable_pdf_has_no_thumbnail(self):
    item = self.item(data=b'%PDF-1.4 not really')
    self.assertIsNone(ensure_preview(item))
    self.assertEqual(self.client.get(f'/content/{item.token}/thumb/card/').status_code, 404)

  def test_other_files_have_none(self):
    item = self.item(data=b'just text', name='notes.txt')
    self.assertFalse(item.has_thumbnail)
    self.assertIsNone(ensure_preview(item))
    self.assertEqual(self.client.get(f'/content/{item.token}/thumb/card/').status_code, 404)

  def test_an_image_card_in_the_list(self):
    item = self.item()
    html = self.client.get('/content/').content.decode().replace('"', '')
    self.assertIn(f'/content/{item.token}/thumb/card/', html)

  def test_the_pdf_may_be_framed_by_the_site_itself(self):
    """The item page shows it in an <iframe>: SAMEORIGIN, not DENY."""
    item = self.item()
    response = self.client.get(f'/content/{item.token}/file/')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')
    self.assertEqual(self.client.get('/content/')['X-Frame-Options'], 'DENY')   # pages stay unframeable

  def test_made_on_upload(self):
    response = self.client.post('/content/new/upload/', {'file': SimpleUploadedFile('Krantje.pdf', pdf('blue'), 'application/pdf')})
    self.assertEqual(response.status_code, 200)
    item = Content.objects.get(original_filename='Krantje.pdf')
    self.assertTrue(default_storage.exists(preview_name(item)))
    self.assertTrue(response.json()['created']['thumb'])      # the dropzone shows it right away
