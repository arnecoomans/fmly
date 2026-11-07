import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from cmnsd.edit.mode import SESSION_KEY
from content.models import Content
from events.models import Event
from places.models import Place


class EventDetailsTests(TestCase):
  """An item's date and places from an event it documents (content/
  event_details.py): offered on its page in edit mode while it has none,
  copied with a click - never set by itself."""

  def setUp(self):
    self.editor = get_user_model().objects.create(username='editor')
    self.editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    self.place = Place.objects.create(name='Soemedang', user=self.editor)
    self.event = Event.objects.create(kind='marriage', year=1910, month=2, day=2, date_qualifier='circa', user=self.editor, status='p')
    self.event.places.add(self.place)
    self.item = Content.objects.create(name='Trouwfoto', kind='photo', user=self.editor, status='c', visibility='c')
    self.item.events.add(self.event)

  def use(self, part, event=None, item=None):
    item = item or self.item
    return self.client.post(f'/api/content/{item.token}/use_event_detail/', json.dumps({'event': (event or self.event).token, 'part': part}), content_type='application/json')

  def page(self):
    session = self.client.session
    session[SESSION_KEY] = True
    session.save()
    return self.client.get(self.item.get_absolute_url()).content.decode().replace('"', '')

  def test_not_set_by_itself(self):
    self.item.refresh_from_db()
    self.assertIsNone(self.item.year)
    self.assertFalse(self.item.places.exists())

  def test_offered_on_the_page(self):
    page = self.page()
    self.assertIn('name=part type=hidden value=date', page)
    self.assertIn('name=part type=hidden value=places', page)

  def test_the_date_with_how_sure(self):
    self.assertEqual(self.use('date').status_code, 200)
    self.item.refresh_from_db()
    self.assertEqual((self.item.year, self.item.month, self.item.day, self.item.date_qualifier), (1910, 2, 2, 'circa'))
    self.assertNotIn('name=part type=hidden value=date', self.page())                  # dated now: no more offer

  def test_the_places(self):
    self.use('places')
    self.assertEqual(list(self.item.places.all()), [self.place])
    self.assertNotIn('name=part type=hidden value=places', self.page())

  def test_a_date_already_is_kept(self):
    Content.objects.filter(pk=self.item.pk).update(year=1912)
    self.assertEqual(self.use('date').status_code, 400)
    self.item.refresh_from_db()
    self.assertEqual(self.item.year, 1912)

  def test_only_a_linked_event(self):
    other = Event.objects.create(kind='birth', year=1880, user=self.editor, status='p')
    self.assertEqual(self.use('date', event=other).status_code, 400)
    self.item.refresh_from_db()
    self.assertIsNone(self.item.year)

  def test_only_who_may_change_it(self):
    viewer = get_user_model().objects.create(username='viewer')
    viewer.save()
    self.client.force_login(viewer)
    published = Content.objects.create(name='Akte', kind='document', user=self.editor, status='p', visibility='c')
    published.events.add(self.event)
    self.assertIn(self.use('date', item=published).status_code, (403, 404))
    published.refresh_from_db()
    self.assertIsNone(published.year)
