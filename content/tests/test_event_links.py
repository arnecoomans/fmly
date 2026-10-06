import json
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import override_settings

from content.models import Content
from events.models import Event
from legacy_import.links import link_event_images
from people.models import Person

from .test_models import MEDIA, ContentTestCase


def write_fixture(directory, links):
  """archive_event.json with {event pk: [image pks]}."""
  rows = [{'pk': event, 'fields': {'images': images}} for event, images in links.items()]
  (Path(directory) / 'archive_event.json').write_text(json.dumps(rows))


@override_settings(MEDIA_ROOT=MEDIA)
class EventLinkTests(ContentTestCase):
  def setUp(self):
    super().setUp()
    self.fixtures = tempfile.mkdtemp()
    write_fixture(self.fixtures, {10: [20]})

  def event(self):
    return Event.objects.create(pk=10, kind=Event.Kind.BIRTH, year=1943, user=self.user)

  def content(self):
    return Content.objects.create(pk=20, name='Geboorte Eric', user=self.user)

  def test_events_first_then_content(self):
    self.event()
    self.assertEqual(link_event_images(self.fixtures), (0, 1))  # waiting for content
    content = self.content()
    self.assertEqual(link_event_images(self.fixtures), (1, 0))
    self.assertEqual(list(content.events.values_list('pk', flat=True)), [10])

  def test_content_first_then_events(self):
    content = self.content()
    self.assertEqual(link_event_images(self.fixtures), (0, 1))  # waiting for the event
    self.event()
    link_event_images(self.fixtures)
    self.assertEqual(list(content.events.values_list('pk', flat=True)), [10])

  def test_rerun_keeps_manual_links(self):
    content = self.content()
    self.event()
    manual = Event.objects.create(pk=11, kind=Event.Kind.HISTORICAL, year=1950, user=self.user)
    content.events.add(manual)
    link_event_images(self.fixtures)
    self.assertEqual(set(content.events.values_list('pk', flat=True)), {10, 11})


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class PersonPageEventContentTests(ContentTestCase):
  def test_only_visible_content_is_linked(self):
    member = get_user_model().objects.create(username='member')
    person = Person.objects.create(given_name='Eric', user=self.user, status='p', visibility='c')
    event = Event.objects.create(kind=Event.Kind.BIRTH, year=1943, user=self.user)
    event.people.add(person)
    shown = Content.objects.create(name='Announcement', user=self.user, status='p', visibility='c')
    hidden = Content.objects.create(name='Private scan', user=self.user, status='p', visibility='q')
    shown.events.add(event)
    hidden.events.add(event)
    self.client.force_login(member)
    html = self.client.get(person.get_absolute_url()).content.decode()
    self.assertIn(shown.get_absolute_url(), html)
    self.assertNotIn(hidden.get_absolute_url(), html)


class NewEventDateTests(ContentTestCase):
  """"+ new event" on an item's page starts on the item's date - a clipping's
  publication date, changeable in the dialog."""

  def test_prefilled(self):
    from django.contrib.auth import get_user_model
    from django.contrib.auth.models import Permission
    from django.test import Client
    from content.models import Content
    user = get_user_model().objects.create(username='redacteur')
    for codename in ('change_content', 'add_event'):
      user.user_permissions.add(Permission.objects.get(codename=codename))
    user.save()
    client = Client()
    client.force_login(user)
    client.post('/ui/edit/', {'on': '1', 'next': '/'})
    clipping = Content.objects.create(name='Overlijdensbericht', kind='document', user=user, status='p', visibility='c', year=1932, month=10, day=8)
    html = client.get(clipping.get_absolute_url()).content.decode().replace('&amp;', '&')
    self.assertIn('/api/event/new/?year=1932&month=10&day=8&date_qualifier=exact', html)
    form = client.get('/api/event/new/', {'year': 1932, 'month': 10, 'day': 8, 'title': 'Overlijden'}).json()['html'].replace('"', '')
    self.assertIn('value=1932', form)
