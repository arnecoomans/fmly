import io
import os

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from content.models import Content

from .test_models import MEDIA, ContentTestCase


def body(response):
  if getattr(response, 'streaming', False):
    return body(response)
  return response.content


def png_bytes():
  buffer = io.BytesIO()
  Image.new('RGB', (800, 600), 'red').save(buffer, 'PNG')
  return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class FileViewTests(ContentTestCase):
  def setUp(self):
    super().setUp()
    self.photo = Content(user=self.user, name='Photo', kind=Content.Kind.PHOTO, status='p', visibility='c')
    self.photo.file = ContentFile(png_bytes(), name='IMG_1.png')
    self.photo.save()
    self.member = get_user_model().objects.create(username='member')

  def file_url(self, content=None):
    return reverse('content:file', args=[(content or self.photo).token])

  def thumb_url(self, preset='card'):
    return reverse('content:thumbnail', args=[self.photo.token, preset])

  def test_anonymous_cannot_see_community_content(self):
    self.assertEqual(self.client.get(self.file_url()).status_code, 404)
    self.assertEqual(self.client.get(self.thumb_url()).status_code, 404)

  def test_signed_in_member_can(self):
    self.client.force_login(self.member)
    response = self.client.get(self.file_url())
    self.assertEqual(response.status_code, 200)
    self.assertEqual(body(response), png_bytes())

  def test_thumbnail_is_generated_inside_private_media(self):
    self.client.force_login(self.member)
    response = self.client.get(self.thumb_url('avatar'))
    self.assertEqual(response.status_code, 200)
    thumb = Image.open(io.BytesIO(body(response)))
    self.assertEqual(thumb.size, (160, 160))
    cached = [f for _, _, files in os.walk(os.path.join(MEDIA, 'cache')) for f in files]
    self.assertTrue(cached)

  def test_unknown_preset_404(self):
    self.client.force_login(self.member)
    self.assertEqual(self.client.get(self.thumb_url('huge')).status_code, 404)

  def test_public_content_visible_anonymously(self):
    Content.objects.filter(pk=self.photo.pk).update(visibility='p')
    self.assertEqual(self.client.get(self.file_url()).status_code, 200)

  def test_missing_file_404(self):
    record = Content.objects.create(user=self.user, name='No file', status='p', visibility='p')
    self.assertEqual(self.client.get(self.file_url(record)).status_code, 404)

  def test_no_thumbnail_for_pdf(self):
    self.client.force_login(self.member)
    pdf = Content(user=self.user, name='A pdf', status='p', visibility='c')
    pdf.file = ContentFile(b'%PDF-1.4', name='a.pdf')
    pdf.save()
    response = self.client.get(reverse('content:thumbnail', args=[pdf.token, 'card']))
    self.assertEqual(response.status_code, 404)


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple',
                   THUMBNAIL_ENGINE='content.thumbnail_engine.Engine')
class DraftEngineTests(ContentTestCase):
  def test_large_jpeg_thumbnails_at_exact_size(self):
    buffer = io.BytesIO()
    Image.new('RGB', (4000, 3000), 'blue').save(buffer, 'JPEG')
    item = Content(user=self.user, name='Big scan', kind=Content.Kind.PHOTO, status='p', visibility='p')
    item.file = ContentFile(buffer.getvalue(), name='IMG_2.jpg')
    item.save()
    for preset, expected in (('avatar', (160, 160)), ('card', (480, 360)), ('large', (1600, 1200))):
      response = self.client.get(reverse('content:thumbnail', args=[item.token, preset]))
      self.assertEqual(Image.open(io.BytesIO(body(response))).size, expected, preset)

  def test_draft_skipped_with_cropbox(self):
    from content.thumbnail_engine import Engine
    image = Image.open(io.BytesIO(self._jpeg()))
    result = Engine().create(image, (100, 100), {'cropbox': '0,0,2000,2000', 'crop': 'center', 'upscale': True,
                                                 'quality': 95, 'orientation': True, 'colorspace': 'RGB',
                                                 'format': 'JPEG', 'padding': False, 'rounded': None, 'blur': None})
    self.assertEqual(result.size, (100, 100))

  def _jpeg(self):
    buffer = io.BytesIO()
    Image.new('RGB', (4000, 3000), 'green').save(buffer, 'JPEG')
    return buffer.getvalue()


class UploaderTests(TestCase):
  """An item's page names who added it and when (Content.user,
  date_created) - for signed-in members only."""

  def setUp(self):
    from django.contrib.auth import get_user_model
    from people.models import Person
    self.uploader = get_user_model().objects.create(username='arne')
    self.person = Person.objects.create(given_name='Arne', last_name='Coomans', user=self.uploader, status='p', visibility='c',
                                        related_user=self.uploader)
    self.uploader.save()
    self.member = get_user_model().objects.create(username='member')
    self.member.save()
    self.item = Content.objects.create(name='Foto', kind='photo', user=self.uploader, status='p', visibility='p')

  def page(self, user=None):
    from django.test import Client
    client = Client()
    if user:
      client.force_login(user)
    return client.get(self.item.get_absolute_url()).content.decode()

  def test_member_sees_who_and_when(self):
    html = self.page(self.member)
    self.assertIn('Added', html)
    self.assertIn('Coomans', html)
    self.assertIn(self.item.date_created.strftime('%Y'), html)

  def test_visitor_does_not(self):
    self.assertNotIn('Added', self.page())

  def test_username_without_a_person(self):
    from django.contrib.auth import get_user_model
    loner = get_user_model().objects.create(username='losse_gebruiker')
    Content.objects.filter(pk=self.item.pk).update(user=loner)
    self.assertIn('losse_gebruiker', self.page(self.member))
