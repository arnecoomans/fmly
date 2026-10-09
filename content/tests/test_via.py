from django.contrib.auth import get_user_model
from django.test import TestCase

from content.models import Content
from core.models import Tag
from events.models import Event
from people.models import Person
from places.models import Place


class ViaTests(TestCase):
  """Issue #455, "via" (cmnsd.js via.js): a tag, place, event or person page
  marks the regions whose links carry ?via_<kind>=<token>; the page they
  lead to marks what can be highlighted. The JS does the rest - here: that
  both sides are in the HTML."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    self.tag = Tag.objects.create(name='Krangan 81', user=self.user, status='p', visibility='c')
    self.place = Place.objects.create(name='Batavia', user=self.user)
    self.person = Person.objects.create(given_name='Corry', user=self.user, status='p', visibility='c')
    self.item = Content.objects.create(name='Trouwfoto', kind='photo', user=self.user, status='p', visibility='c')
    self.item.tags.add(self.tag)
    self.item.places.add(self.place)
    self.item.people.add(self.person)
    self.person.tags.add(self.tag)
    self.event = Event.objects.create(kind=Event.Kind.MARRIAGE, year=1941, user=self.user)
    self.event.people.add(self.person)
    self.event.places.add(self.place)
    self.item.events.add(self.event)

  def html(self, url):
    return self.client.get(url).content.decode().replace('"', '')

  def test_sources_mark_their_regions(self):
    for obj, kind in ((self.tag, 'tag'), (self.place, 'place'), (self.event, 'event'), (self.person, 'person')):
      self.assertIn(f'data-cmnsd-via-links={kind}:{obj.token}', self.html(obj.get_absolute_url()), kind)

  def test_destinations_mark_what_can_be_highlighted(self):
    item = self.html(self.item.get_absolute_url())
    for kind, obj in (('tag', self.tag), ('place', self.place), ('person', self.person), ('event', self.event)):
      self.assertIn(f'data-cmnsd-via={kind}:{obj.token}', item, kind)          # the item's tags, places, people, events
    event = self.html(self.event.get_absolute_url())
    for kind, obj in (('person', self.person), ('place', self.place)):
      self.assertIn(f'data-cmnsd-via={kind}:{obj.token}', event, kind)

  def test_person_page_comments_are_no_region(self):
    html = self.html(self.person.get_absolute_url())
    self.assertEqual(html.count(f'data-cmnsd-via-links=person:{self.person.token}'), 4)   # tags, relationships, content, events
