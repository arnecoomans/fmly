import shutil
import tempfile

from django.contrib.admin import helpers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, override_settings

from content.models import Content
from people.models import Person


class PartsTests(TestCase):
  """Parts for every kind: Content.parent + position. Position 0 = a
  variant of the whole; the same number twice = variants of each other."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='admin', is_staff=True, is_superuser=True)
    self.client.force_login(self.user)
    item = lambda name, kind='photo': Content.objects.create(name=name, kind=kind, user=self.user, status='p', visibility='c')
    self.front = item('Postcard front')
    self.back = item('Postcard back')
    self.colorized = item('Postcard front, colorized')

  def test_make_parts_of_numbers_in_order(self):
    self.assertEqual(self.front.make_parts_of([self.back, self.colorized]), 2)
    self.assertEqual([(p.name, p.position) for p in self.front.parts.order_by('position')],
                     [('Postcard back', 1), ('Postcard front, colorized', 2)])
    self.assertNotIn(self.back, Content.objects.listable())

  def test_one_level_only(self):
    self.front.make_parts_of([self.back])
    other = Content.objects.create(name='Other', user=self.user)
    with self.assertRaises(ValidationError):
      self.back.make_parts_of([other])            # a part can't be a whole
    with self.assertRaises(ValidationError):
      other.make_parts_of([self.front])           # a whole with parts can't become a part
    self.assertIsNone(Content.objects.get(pk=other.pk).parent)

  def test_variant_shown_with_the_item_other_parts_numbered(self):
    self.front.make_parts_of([self.back, self.colorized])
    Content.objects.filter(pk=self.colorized.pk).update(position=0)
    response = self.client.get(self.front.get_absolute_url())
    self.assertEqual([p.name for p in response.context['variants']], ['Postcard front, colorized'])
    self.assertEqual([p.name for p in response.context['parts']], ['Postcard back'])

  def test_person_linked_to_a_part_gets_the_whole(self):
    self.front.make_parts_of([self.back])
    eric = Person.objects.create(given_name='Eric', user=self.user, status='p', visibility='c')
    self.back.people.add(eric)
    request = RequestFactory().get('/')
    request.user = get_user_model().objects.get(pk=self.user.pk)
    self.assertEqual([c.name for c in eric.get_visible_content(request)], ['Postcard front'])

  def test_admin_action_confirms_then_applies(self):
    url = '/admin/content/content/'
    selected = [self.back.pk, self.front.pk, self.colorized.pk]
    page = self.client.post(url, {'action': 'make_parts', helpers.ACTION_CHECKBOX_NAME: selected})
    self.assertContains(page, 'Which of these is the whole?')
    self.client.post(url, {'action': 'make_parts', 'apply': '1', 'lead': self.front.pk,
                           helpers.ACTION_CHECKBOX_NAME: selected})
    self.assertEqual(set(self.front.parts.values_list('name', flat=True)), {'Postcard back', 'Postcard front, colorized'})

  def test_parts_inline_on_every_kind_but_not_on_a_part(self):
    self.front.make_parts_of([self.back])
    self.assertContains(self.client.get(f'/admin/content/content/{self.front.pk}/change/'), 'parts-group')
    self.assertNotContains(self.client.get(f'/admin/content/content/{self.back.pk}/change/'), 'parts-group')


MEDIA = tempfile.mkdtemp()


# The pages are saved with an image: into a temporary MEDIA_ROOT, never the
# real private/ (subclasses inherit it).
@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class PartBrowsingTests(TestCase):
  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    from django.core.files.base import ContentFile
    from .test_views import png_bytes
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    def item(name, image=True):
      content = Content(name=name, kind='book', user=self.user, status='p', visibility='c')
      if image:
        content.file = ContentFile(png_bytes(), name='IMG_1.png')
      content.save()
      return content
    self.book = item('Book')
    self.pages = [item(f'Page {i}') for i in (1, 2, 3)]
    self.book.make_parts_of(self.pages)

  def test_whole_page_gets_the_sequence(self):
    context = self.client.get(self.book.get_absolute_url()).context
    self.assertEqual([i['title'] for i in context['gallery']], ['Book', 'Page 1', 'Page 2', 'Page 3'])

  def test_part_page_has_previous_and_next(self):
    context = self.client.get(self.pages[1].get_absolute_url()).context
    self.assertEqual((context['sibling_index'], context['sibling_count']), (2, 3))
    self.assertEqual((context['previous_part'], context['next_part']), (self.pages[0], self.pages[2]))
    first = self.client.get(self.pages[0].get_absolute_url()).context
    self.assertIsNone(first['previous_part'])

  def test_no_gallery_without_a_whole_image(self):
    from django.db.models.fields.files import FieldFile
    Content.objects.filter(pk=self.book.pk).update(file='')
    self.assertEqual(self.client.get(self.book.get_absolute_url()).context['gallery'], [])


class PartsSectionTests(PartBrowsingTests):
  def test_collapsible_and_still_rendered_when_closed(self):
    import json
    html = self.client.get(self.book.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-section=content.parts open', html)
    self.client.post('/ui/section/', json.dumps({'key': 'content.parts', 'open': False}), content_type='application/json')
    html = self.client.get(self.book.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-section=content.parts>', html)                 # closed...
    self.assertIn(f'href={self.pages[1].get_absolute_url()}', html)          # ...but the thumbnails are there - links to the parts' pages
    self.assertNotIn('data-gallery-show', html)                               # (not shown in place: the arrows do that)
    self.assertIn('title=Page 2', html)                                        # name as tooltip, no caption


class PartsGroupTests(PartBrowsingTests):
  def test_whole_counts_itself_and_leads_the_group(self):
    context = self.client.get(self.book.get_absolute_url()).context
    self.assertEqual([c.name for c in context['group']], ['Book', 'Page 1', 'Page 2', 'Page 3'])
    html = self.client.get(self.book.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('Parts <span class=page-section__count>4</span>', html)

  def test_part_page_shows_the_group_with_itself_marked(self):
    response = self.client.get(self.pages[1].get_absolute_url())
    self.assertEqual([c.name for c in response.context['group']], ['Book', 'Page 1', 'Page 2', 'Page 3'])
    html = response.content.decode().replace('"', '')
    self.assertIn('content-part is-current', html)
    # Browsing on a part's page too: the whole group, in order, starting at this part.
    self.assertEqual([i['title'] for i in response.context['gallery']], ['Book', 'Page 1', 'Page 2', 'Page 3'])
    self.assertEqual(response.context['gallery_start'], 2)
    self.assertIn('data-gallery-start=2', html)
    self.assertIn('<span data-gallery-counter>3 / 4</span>', html)
    self.assertIn('data-lightbox-items=#content-gallery-items', html)          # full-screen through the parts too
