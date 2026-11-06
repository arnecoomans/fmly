from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from events.models import Event
from people.models import Person
from places.models import Place


class CreateWithBirthAndDeathTests(TestCase):
  """Birth and death in the new-person form (PersonCreateForm, the dialog
  and /people/new/): the page's block forms, prefixed - an event each,
  linked to the new person; nothing filled in, no event."""

  def setUp(self):
    self.editor = get_user_model().objects.create(username='editor')
    for codename in ('add_person', 'change_person', 'add_event', 'add_place'):
      self.editor.user_permissions.add(Permission.objects.get(codename=codename))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    self.place = Place.objects.create(name='Soemedang', user=self.editor)
    self.child = Person.objects.create(given_name='Kind', last_name='Bake', user=self.editor, status='p', visibility='c')

  def create(self, **data):
    data = {'given_name': 'Willem', 'last_name': 'Bake', 'gender': 'm', 'family_connection': 'family', 'visibility': 'c',
            'birth-date_qualifier': 'exact', 'death-date_qualifier': 'exact', **data}
    return self.client.post('/api/person/new/', data)

  def test_nothing_filled_in_no_events(self):
    self.assertEqual(self.create().status_code, 200)
    self.assertFalse(Event.objects.exists())

  def test_birth_and_death_made(self):
    response = self.create(**{'birth-year': '1880', 'birth-month': '3', 'birth-place': self.place.token, 'death-date_qualifier': 'circa', 'death-year': '1950'})
    self.assertEqual(response.status_code, 200)
    person = Person.objects.get(given_name='Willem')
    self.assertEqual((person.birth.year, person.birth.month, list(person.birth.places.all())), (1880, 3, [self.place]))
    self.assertEqual((person.death.year, person.death.date_qualifier), (1950, 'circa'))

  def test_died_details_unknown(self):
    self.create(**{'death-record': '1'})
    death = Person.objects.get(given_name='Willem').death
    self.assertIsNotNone(death)
    self.assertIsNone(death.year)

  def test_a_new_place_typed(self):
    self.create(**{'birth-year': '1880', 'birth-place__new': 'Buitenzorg'})
    self.assertEqual(list(Person.objects.get(given_name='Willem').birth.places.values_list('name', flat=True)), ['Buitenzorg'])

  def test_an_invalid_date_saves_nothing(self):
    response = self.create(**{'birth-year': '1880', 'birth-month': '2', 'birth-day': '31'})
    self.assertEqual(response.status_code, 400)
    self.assertFalse(Person.objects.filter(given_name='Willem').exists())
    self.assertFalse(Event.objects.exists())

  def test_the_death_row_open_for_a_parent(self):
    closed = self.client.get('/api/person/new/', {'relative_of': self.child.token, 'added_as': 'child'}).json()['html'].replace('"', '')
    self.assertRegex(closed, r'<details class=[^>]*person-create__death>')
    opened = self.client.get('/api/person/new/', {'relative_of': self.child.token, 'added_as': 'parent'}).json()['html'].replace('"', '')
    self.assertRegex(opened, r'<details class=[^>]*person-create__death[^>]* open>|<details [^>]*open[^>]*person-create__death')

  def test_on_the_page_too(self):
    response = self.client.post('/people/new/', {'given_name': 'Anna', 'last_name': 'Bake', 'gender': 'f', 'family_connection': 'family', 'visibility': 'c',
                                                 'birth-date_qualifier': 'exact', 'birth-year': '1901', 'death-date_qualifier': 'exact'})
    person = Person.objects.get(given_name='Anna')
    self.assertEqual(person.birth.year, 1901)
    self.assertNotIn('open=birth', response['Location'])                   # given here: not opened on the page
