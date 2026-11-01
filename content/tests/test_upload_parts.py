import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from content.models import Content
from content.tests.test_upload import jpeg

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class UploadPartsTests(TestCase):
  """Adding pages to an item that's in the archive (issue #485):
  content_upload's `whole` makes each new file its next part - taking over
  its visibility, and for a document or book the kind document - and a
  loose item that has the file already becomes the part; the dropzone
  under the parts."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = self.make_user('pagina', 'add_content', 'change_content')
    self.client = Client()
    self.client.force_login(self.user)
    self.almanac = Content.objects.create(name='Regeeringsalmanak', kind='document', year=1874, user=self.user, status='p', visibility='f')
    Content.objects.create(name='1870', kind='document', year=1870, parent=self.almanac, position=1, user=self.user, status='p', visibility='f')

  def make_user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def upload(self, whole, name, color='white', client=None):
    body = {'file': SimpleUploadedFile(name, jpeg(color), 'image/jpeg'), 'whole': whole}
    return (client or self.client).post('/content/new/upload/', body)

  def parts(self):
    return list(self.almanac.parts.order_by('position').values_list('position', 'kind', 'visibility', 'year', 'status'))

  def test_new_files_become_its_next_parts(self):
    for name, color in (('scan_001.jpg', 'red'), ('scan_002.jpg', 'blue')):
      self.assertEqual(self.upload(self.almanac.token, name, color).status_code, 200)
    self.assertEqual(self.parts(), [
      (1, 'document', 'f', 1870, 'p'),
      (2, 'document', 'f', None, 'c'),                                          # its visibility and kind - not its year; a draft
      (3, 'document', 'f', None, 'c'),
    ])

  def test_a_loose_item_with_the_file_becomes_the_part(self):
    loose = Content.objects.create(name='Losse pagina', kind='document', user=self.user, status='p', visibility='c')
    self.upload(self.almanac.token, 'losse.jpg', 'green')                       # the file of a part - then make it loose again
    copy = self.almanac.parts.get(position=2)
    copy.parent, copy.position = None, 0
    copy.save()
    response = self.upload(self.almanac.token, 'nogmaals.jpg', 'green').json()
    self.assertTrue(response['duplicate']['linked'])
    copy.refresh_from_db()
    self.assertEqual((copy.parent_id, copy.position), (self.almanac.pk, 2))
    self.assertIsNone(Content.objects.get(pk=loose.pk).parent_id)

  def test_a_part_elsewhere_is_only_reported(self):
    other = Content.objects.create(name='Ander album', kind='photo', user=self.user, status='p', visibility='c')
    self.upload(other.token, 'album.jpg', 'yellow')
    response = self.upload(self.almanac.token, 'album-kopie.jpg', 'yellow').json()
    self.assertFalse(response['duplicate']['linked'])
    self.assertEqual(len(self.parts()), 1)                                       # nothing moved

  def test_refusals(self):
    part = self.almanac.parts.get()
    self.assertEqual(self.upload(part.token, 'x.jpg').status_code, 400)        # a part isn't a whole
    self.assertEqual(self.upload('nosuchtoken', 'x.jpg').status_code, 400)
    reader = self.make_user('lezer3', 'add_content')                           # may add, not change this item
    stranger = Content.objects.create(name='Openbaar', kind='document', user=self.user, status='p', visibility='c')
    client = Client()
    client.force_login(reader)
    self.assertEqual(self.upload(stranger.token, 'x.jpg', client=client).status_code, 403)
    self.assertEqual(Content.objects.filter(parent__isnull=False).count(), 1)

  def test_the_dropzone_under_the_parts(self):
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    page = self.client.get(self.almanac.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'name=whole type=hidden value={self.almanac.token}', page.replace('data-upload-param ', '').replace(' data-upload-param', ''))
    self.assertIn('data-upload-reload', page)
