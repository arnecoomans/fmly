from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.files.base import ContentFile
from django.test import override_settings
from django.urls import reverse

from content.models import Content, Portrait
from content.templatetags.content_tags import visible_portrait
from people.models import Person

from .test_models import MEDIA, ContentTestCase
from .test_views import png_bytes


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class PortraitAvatarTests(ContentTestCase):
  def setUp(self):
    super().setUp()
    self.member = get_user_model().objects.create(username='member')
    self.person = Person.objects.create(given_name='Eric', user=self.user, status='p', visibility='p')

  def portrait(self, kind=Content.Kind.PHOTO, visibility='c', **crop):
    content = Content(user=self.user, name='Portrait', kind=kind, status='p', visibility=visibility)
    content.file = ContentFile(png_bytes(), name='IMG_1.png')
    content.save()
    Portrait.objects.create(person=self.person, content=content, is_primary=True, **crop)
    return Person.objects.get(pk=self.person.pk)

  def test_photo_portrait_shown_to_member(self):
    self.assertIsNotNone(visible_portrait(self.portrait(), self.member))

  def test_hidden_photo_falls_back_for_anonymous(self):
    # Public person, community photo: signed-out visitors get initials.
    self.assertIsNone(visible_portrait(self.portrait(), AnonymousUser()))

  def test_document_portrait_needs_crop(self):
    person = self.portrait(kind=Content.Kind.DOCUMENT)
    self.assertIsNone(visible_portrait(person, self.member))
    Portrait.objects.filter(person=person).update(crop_x=0.1, crop_y=0.1, crop_w=0.3, crop_h=0.3)
    self.assertIsNotNone(visible_portrait(Person.objects.get(pk=person.pk), self.member))

  def test_no_portrait(self):
    self.assertIsNone(visible_portrait(self.person, self.member))

  def test_row_renders_avatar_image(self):
    self.portrait()
    self.client.force_login(self.member)
    response = self.client.get(reverse('people:person_list'))
    self.assertContains(response, f'/portrait/{self.person.token}/?v=full')


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class ContentDetailTests(ContentTestCase):
  def setUp(self):
    super().setUp()
    self.member = get_user_model().objects.create(username='member')
    self.item = Content(user=self.user, name='Trouwfoto', kind=Content.Kind.PHOTO, status='p', visibility='c')
    self.item.file = ContentFile(png_bytes(), name='IMG_1.png')
    self.item.save()

  def test_visibility(self):
    url = self.item.get_absolute_url()
    self.assertEqual(self.client.get(url).status_code, 404)
    self.client.force_login(self.member)
    response = self.client.get(url)
    self.assertContains(response, 'Trouwfoto')
    self.assertContains(response, reverse('content:thumbnail', args=[self.item.token, 'large']))

  def test_book_shows_visible_parts_in_order(self):
    book = Content.objects.create(user=self.user, name='Bushido', kind=Content.Kind.BOOK, status='p', visibility='c')
    Content.objects.create(user=self.user, name='Excerpt', parent=book, position=2, status='p', visibility='c')
    Content.objects.create(user=self.user, name='Back cover', parent=book, position=1, status='p', visibility='c')
    Content.objects.create(user=self.user, name='Draft part', parent=book, position=3, status='c', visibility='c')
    self.client.force_login(self.member)
    html = self.client.get(book.get_absolute_url()).content.decode()
    self.assertLess(html.index('Back cover'), html.index('Excerpt'))
    self.assertNotIn('Draft part', html)

  def test_missing_file_message(self):
    record = Content.objects.create(user=self.user, name='No file', status='p', visibility='p', original_filename='cover.JPG')
    self.assertContains(self.client.get(record.get_absolute_url()), 'cover.JPG')


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class ContentDetailLinkedAccessTests(ContentTestCase):
  def test_deleted_person_and_tag_not_listed(self):
    from core.models import Tag
    member = get_user_model().objects.create(username='member')
    item = Content.objects.create(user=self.user, name='Photo', status='p', visibility='c')
    item.people.add(
      Person.objects.create(given_name='Shown', user=self.user, status='p', visibility='c'),
      Person.objects.create(given_name='Removed', user=self.user, status='x', visibility='c'),
    )
    item.tags.add(
      Tag.objects.create(name='shown-tag', user=self.user, status='p', visibility='p'),
      Tag.objects.create(name='removed-tag', user=self.user, status='x', visibility='p'),
    )
    self.client.force_login(member)
    html = self.client.get(item.get_absolute_url()).content.decode()
    self.assertIn('Shown', html)
    self.assertNotIn('Removed', html)
    self.assertIn('shown-tag', html)
    self.assertNotIn('removed-tag', html)
