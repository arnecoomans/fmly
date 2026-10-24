import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from content.models import Content
from content.tests.test_upload import jpeg
from content.uploads import checksum_of, find_duplicate

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class ReplaceFileTests(TestCase):
  """Another file for an existing item (a better scan, through the admin):
  its checksum and original name follow - a replaced file is recognised as
  in the archive, the old one's fingerprint no longer points here."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def test_checksum_follows_the_file(self):
    user = get_user_model().objects.create(username='scan')
    first = SimpleUploadedFile('scan_klein.jpg', jpeg(size=(40, 30)), content_type='image/jpeg')
    item = Content.objects.create(name='Kerstfeest', kind='photo', file=first, user=user, status='p', visibility='c')
    old = item.checksum
    self.assertEqual(old, checksum_of(SimpleUploadedFile('x.jpg', jpeg(size=(40, 30)))))   # computed when none came along
    item.file = SimpleUploadedFile('scan_groot.jpg', jpeg(size=(80, 60)), content_type='image/jpeg')
    item.save()
    item.refresh_from_db()
    self.assertNotEqual(item.checksum, old)
    self.assertEqual(find_duplicate(item.checksum), item)                      # the new scan: recognised
    self.assertIsNone(find_duplicate(old))                                     # the old one: no longer here
    self.assertEqual(item.original_filename, 'scan_groot.jpg')
    self.assertEqual((item.width, item.height), (80, 60))
