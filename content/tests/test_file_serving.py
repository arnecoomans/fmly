import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from content.models import Content

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class FileServingTests(TestCase):
  """The original file (content_file): media opens inline; anything else -
  an SVG, an HTML page - downloads, sandboxed: a script in an upload never
  runs as the site."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = get_user_model().objects.create(username='viewer')
    self.client = Client()
    self.client.force_login(self.user)

  def get(self, name, body):
    item = Content(user=self.user, name='Bestand', kind='unknown', status='p', visibility='c', original_filename=name)
    item.file = SimpleUploadedFile(name, body)
    item.save()
    return self.client.get(f'/content/{item.token}/file/')

  def test_a_script_never_runs_as_the_site(self):
    for name, body in (('kaart.svg', b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'), ('pagina.html', b'<script>alert(1)</script>')):
      response = self.get(name, body)
      self.assertEqual(response.status_code, 200)
      self.assertTrue(response['Content-Disposition'].startswith('attachment'), name)
      self.assertIn(name, response['Content-Disposition'])                     # under its own name
      self.assertEqual(response['Content-Security-Policy'], 'sandbox')

  def test_media_inline(self):
    response = self.get('foto.png', b'\x89PNG\r\n\x1a\n')
    self.assertTrue(response['Content-Disposition'].startswith('inline'))
    self.assertEqual(response['Content-Security-Policy'], 'sandbox')
    response = self.get('akte.pdf', b'%PDF-1.4')
    self.assertTrue(response['Content-Disposition'].startswith('inline'))
    self.assertNotIn('Content-Security-Policy', response)                    # Chrome shows no PDF in a sandbox
