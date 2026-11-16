import os
import shutil
import tempfile
from io import StringIO

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from content.models import Content

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA)
class ContentAddTests(TestCase):
  """manage.py content_add: files too big for the web uploader, added the
  uploader's way - a draft in someone's inbox."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    User = get_user_model()
    self.root = User.objects.create(username='beheer', is_superuser=True, is_staff=True)
    self.editor = User.objects.create(username='redacteur')
    self.editor.user_permissions.add(Permission.objects.get(codename='add_content'))
    self.incoming = tempfile.mkdtemp()
    self.addCleanup(shutil.rmtree, self.incoming, ignore_errors=True)

  def file(self, name, body=b'recording'):
    path = os.path.join(self.incoming, name)
    with open(path, 'wb') as handle:
      handle.write(body)
    return path

  def add(self, *args):
    out = StringIO()
    call_command('content_add', *args, stdout=out, stderr=StringIO())
    return out.getvalue()

  def test_a_draft_in_the_named_inbox(self):
    out = self.add(self.file('Oma 80 jaar.mp4'), '--user', 'redacteur')
    item = Content.objects.get()
    self.assertEqual((item.user, item.status, item.kind, item.name), (self.editor, Content.Status.CONCEPT, Content.Kind.RECORDING, 'Oma 80 jaar'))
    self.assertTrue(item.checksum)
    self.assertTrue(LogEntry.objects.filter(object_id=str(item.pk), change_message__contains='content_add').exists())
    self.assertIn("1 added to redacteur's inbox", out)

  def test_the_first_superuser_when_no_user(self):
    out = self.add(self.file('podcast.mp3'))
    self.assertEqual(Content.objects.get().user, self.root)
    self.assertIn('the first superuser', out)

  def test_a_folder_and_a_duplicate(self):
    self.file('a.mp3', b'one')
    self.file('b.mp3', b'two')
    self.file('.DS_Store', b'hidden')
    self.add(self.incoming)
    self.assertEqual(Content.objects.count(), 2)
    out = self.add(self.file('again.mp3', b'one'), '--delete-source')
    self.assertIn('in the archive already', out)
    self.assertEqual(Content.objects.count(), 2)
    self.assertTrue(os.path.exists(os.path.join(self.incoming, 'again.mp3')))   # a duplicate's source stays

  def test_delete_source(self):
    path = self.file('lang.mp4')
    self.add(path, '--delete-source')
    self.assertFalse(os.path.exists(path))
    self.assertTrue(os.path.exists(Content.objects.get().file.path))

  def test_a_format_browsers_cant_play(self):
    self.assertIn("browsers can't play", self.add(self.file('dvd.avi')))
    self.assertNotIn("browsers can't play", self.add(self.file('goed.mp4', b'other')))

  def test_only_as_the_owner_of_the_uploads(self):
    """Not as the admin or root - the site's files would belong to them."""
    from unittest import mock
    path = self.file('x.mp3')
    with mock.patch('os.geteuid', return_value=os.stat(MEDIA).st_uid + 1):
      with self.assertRaisesMessage(CommandError, 'sudo -u'):
        self.add(path)
    self.assertFalse(Content.objects.exists())

  def test_refused(self):
    reader = get_user_model().objects.create(username='lezer')
    with self.assertRaisesMessage(CommandError, 'may not upload'):
      self.add(self.file('x.mp3'), '--user', reader.username)
    with self.assertRaisesMessage(CommandError, "No user 'niemand'"):
      self.add(self.file('x.mp3'), '--user', 'niemand')
    with self.assertRaisesMessage(CommandError, 'Not a file or folder'):
      self.add(os.path.join(self.incoming, 'nope.mp3'))
    self.assertFalse(Content.objects.exists())
