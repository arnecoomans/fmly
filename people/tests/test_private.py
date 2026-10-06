from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from people.models import Person, PersonRelation


class PrivatePersonTests(TestCase):
  """A private person (Person.private, people/privacy.py): their page opens
  for themself, their parents and staff; for everyone else the name shows,
  without a link, and the address is "not found"."""

  def setUp(self):
    User = get_user_model()
    make = lambda given, **f: Person.objects.create(given_name=given, last_name='Bake', user=self.owner, status='p', visibility='c', **f)
    self.owner = User.objects.create(username='beheer', is_staff=True)
    self.parent_user, self.child_user, self.other_user = (User.objects.create(username=n) for n in ('ouder', 'kind', 'ander'))
    for user in (self.owner, self.parent_user, self.child_user, self.other_user):
      user.save()
    self.parent = make('Ouder', related_user=self.parent_user)
    self.child = make('Kind', private=True, related_user=self.child_user)
    make('Ander', related_user=self.other_user)
    PersonRelation.objects.create(person_from=self.parent, person_to=self.child, relation_type=PersonRelation.RelationType.PARENT)

  def client_for(self, user):
    client = Client()
    client.force_login(user)
    return client

  def test_who_opens_the_page(self):
    url = self.child.page_url()
    self.assertEqual(self.client_for(self.parent_user).get(url).status_code, 200)   # a parent
    self.assertEqual(self.client_for(self.child_user).get(url).status_code, 200)    # themself
    self.assertEqual(self.client_for(self.other_user).get(url).status_code, 404)
    self.assertEqual(self.client_for(self.owner).get(url).status_code, 200)         # staff
    self.assertEqual(self.client_for(self.parent_user).get(f'/person/{self.child.token}/').status_code, 301)
    self.assertEqual(self.client_for(self.other_user).get(f'/person/{self.child.token}/').status_code, 404)

  def test_named_but_not_linked_for_others(self):
    page = self.parent.page_url()
    other = self.client_for(self.other_user).get(page).content.decode().replace('"', '')
    self.assertIn('Kind', other)
    self.assertNotIn(f'href={self.child.page_url()}', other)
    parent = self.client_for(self.parent_user).get(page).content.decode().replace('"', '')
    self.assertIn(f'href={self.child.page_url()}', parent)
    self.assertIsNone(self.child.get_absolute_url())                                   # no address without a viewer

  def test_search_lists_without_a_link(self):
    html = self.client_for(self.other_user).get('/search/', {'q': 'kind'}).content.decode().replace('"', '')
    self.assertIn('Kind', html)
    self.assertNotIn('href=None', html)
    self.assertNotIn(f'href={self.child.page_url()}', html)


class DeathFieldTests(TestCase):
  """The death row in edit mode: an offer when none is recorded, "add date"
  when it's recorded without one; outside edit mode "date unknown"."""

  def setUp(self):
    from django.contrib.auth.models import Permission
    from events.models import Event
    self.Event = Event
    self.editor = get_user_model().objects.create(username='redacteur')
    self.editor.user_permissions.add(Permission.objects.get(codename='change_person'))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)

  def page(self, person, edit):
    self.client.post('/ui/edit/', {'on': '1' if edit else '0', 'next': '/'})
    return self.client.get(person.page_url()).content.decode()

  def test_rows(self):
    living = Person.objects.create(given_name='Levend', user=self.editor, status='p', visibility='c')
    self.assertIn('add death record', self.page(living, edit=True))
    self.assertNotIn('add death record', self.page(living, edit=False))
    gone = Person.objects.create(given_name='Overleden', user=self.editor, status='p', visibility='c')
    self.Event.objects.create(kind='death', user=self.editor).people.set([gone])
    self.assertIn('add date', self.page(gone, edit=True))
    self.assertIn('date unknown', self.page(gone, edit=False))

  def test_birth_row_and_recording_a_death_without_details(self):
    person = Person.objects.create(given_name='Iemand', user=self.editor, status='p', visibility='c')
    self.assertIn('add birth record', self.page(person, edit=True))
    form = self.client.get(f'/api/person/{person.token}/form/death/').json()['html']
    self.assertIn('Died, details unknown', form)
    person.refresh_from_db()
    modified = {'_modified': person.date_modified.isoformat(), 'death-date_qualifier': 'exact'}
    self.assertEqual(self.client.post(f'/api/person/{person.token}/form/death/', modified).status_code, 200)   # empty Save: nothing
    self.assertFalse(self.Event.objects.filter(kind='death', people=person).exists())
    person.refresh_from_db()
    self.client.post(f'/api/person/{person.token}/form/death/', {'_modified': person.date_modified.isoformat(), 'death-date_qualifier': 'exact', 'death-record': '1'})
    death = self.Event.objects.get(kind='death', people=person)
    self.assertIsNone(death.year)
    self.assertIn('date unknown', self.page(person, edit=False))
