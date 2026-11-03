import re

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content, ContentPerson
from events.models import Event
from people.models import Person
from places.models import Place


class EventFromItemTests(TestCase):
  """"Make an event from this item" (issue #487, events.forms
  EventCreateForm ?from_item=): the item's people and places to tick, the
  item linked as proof; by role moved (the item's link removed) or copied;
  a frame is never moved; a refused event moves nothing."""

  def setUp(self):
    self.editor = get_user_model().objects.create(username='redactie')
    for codename in ('add_event', 'change_content', 'add_content'):
      self.editor.user_permissions.add(Permission.objects.get(codename=codename))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    person = lambda name: Person.objects.create(given_name=name, user=self.editor, status='p', visibility='c')
    self.bride, self.groom, self.parent, self.seen = person('Marie'), person('Pieter'), person('Vader'), person('Gast')
    self.place = Place.objects.create(name='Soemedang', user=self.editor)
    self.ad = Content.objects.create(name='Advertentie', kind='document', year=1910, user=self.editor, status='p', visibility='c')
    self.ad.places.add(self.place)
    ContentPerson.objects.create(content=self.ad, person=self.bride)
    ContentPerson.objects.create(content=self.ad, person=self.groom, role='subject')
    ContentPerson.objects.create(content=self.ad, person=self.parent, role='creator')
    ContentPerson.objects.create(content=self.ad, person=self.seen, role='depicted')

  def dialog(self, item=None):
    return self.client.get(f'/api/event/new/?from_item={(item or self.ad).token}&year=1910').json()['html'].replace('"', '')

  def make(self, people, places=(), kind='marriage', item=None):
    data = {'kind': kind, 'date_qualifier': 'exact', 'year': '1910', 'from_item': (item or self.ad).token,
            'item_people': [p.token for p in people], 'item_places': [p.token for p in places]}
    return self.client.post('/api/event/new/', data)

  def on_item(self, item=None):
    return set((item or self.ad).people.all())

  def test_the_dialog_ticks_by_role(self):
    html = self.dialog()
    for person, ticked in ((self.bride, True), (self.groom, True), (self.seen, True), (self.parent, False)):
      tag = re.search(rf'<input[^>]*name=item_people[^>]*value={person.token}[^>]*>', html).group(0)
      self.assertEqual('checked' in tag, ticked, person)
    self.assertIn(f'value={self.place.token}', html)
    self.assertNotIn('data-cmnsd-picker=content', html)                       # the item itself is the proof

  def test_moved_and_copied(self):
    self.assertEqual(self.make([self.bride, self.groom, self.parent, self.seen], [self.place]).status_code, 200)
    event = Event.objects.get(kind='marriage')
    self.assertEqual(set(event.people.all()), {self.bride, self.groom, self.parent, self.seen})
    self.assertEqual(list(event.content.all()), [self.ad])
    self.assertEqual(list(event.places.all()), [self.place])
    self.assertEqual(self.on_item(), {self.parent, self.seen})                # no role and subject moved; creator, depicted stay

  def test_unticked_stay_where_they_are(self):
    self.make([self.bride])
    self.assertEqual(set(Event.objects.get(kind='marriage').people.all()), {self.bride})
    self.assertEqual(self.on_item(), {self.groom, self.parent, self.seen})

  def test_a_frame_is_never_moved(self):
    ContentPerson.objects.filter(content=self.ad, person=self.bride).update(region_x=.1, region_y=.1, region_w=.2, region_h=.2)
    self.make([self.bride])
    self.assertIn(self.bride, self.on_item())

  def test_a_refused_event_moves_nothing(self):
    response = self.make([self.bride, self.groom], kind='birth')             # a birth is one person's
    self.assertEqual(response.status_code, 400)
    self.assertFalse(Event.objects.filter(kind='birth').exists())
    self.assertEqual(self.on_item(), {self.bride, self.groom, self.parent, self.seen})

  def test_on_a_part_the_part_is_the_proof(self):
    part = Content.objects.create(name='Pagina 2', kind='document', parent=self.ad, position=1, user=self.editor, status='p', visibility='c')
    ContentPerson.objects.create(content=part, person=self.bride)
    self.make([self.bride], item=part)
    self.assertEqual(list(Event.objects.get(kind='marriage').content.all()), [part])
    self.assertEqual(self.on_item(part), set())
    self.assertIn(self.bride, self.on_item())                                 # the whole's own link isn't touched

  def test_only_for_an_item_you_may_change(self):
    reader = get_user_model().objects.create(username='lezer4')
    reader.user_permissions.add(Permission.objects.get(codename='add_event'))
    reader.save()
    self.client.force_login(reader)
    html = self.dialog()
    self.assertNotIn(f'value={self.bride.token}', html)                       # no people to move
    self.make([self.bride, self.groom])
    self.assertEqual(self.on_item(), {self.bride, self.groom, self.parent, self.seen})
    self.assertFalse(Event.objects.get(kind='marriage').content.exists())      # nor linked as its proof

  def test_the_button_on_the_item_page(self):
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    page = self.client.get(self.ad.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'from_item={self.ad.token}', page)
    self.assertIn('title=Advertentie', page)                                  # its name, to rewrite
    undated = Content.objects.create(name='Zonder datum', kind='document', user=self.editor, status='p', visibility='c')
    self.assertNotIn('from_item=', self.client.get(undated.get_absolute_url()).content.decode())   # a timeline needs a date

  def test_the_title_suggested(self):
    html = self.client.get(f'/api/event/new/?from_item={self.ad.token}&year=1910&title=Advertentie').json()['html'].replace('"', '')
    self.assertRegex(html, r'name=title[^>]*value=Advertentie')
