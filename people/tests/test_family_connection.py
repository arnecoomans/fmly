from django.contrib.auth import get_user_model
from django.test import TestCase

from people.models import Person, PersonRelation


class FamilyConnectionTests(TestCase):
  """Person.family_connection: family (default) / possibly_family / outsider."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    make = lambda name, connection: Person.objects.create(
      given_name=name, user=self.user, status='p', visibility='c', family_connection=connection)
    self.eric = make('Eric', 'family')
    self.cornelis = make('Cornelis', 'possibly_family')
    self.author = make('Schrijver', 'outsider')

  def listed(self, query=''):
    return {p.given_name for p in self.client.get('/people/' + query).context['person_list']}

  def test_list_shows_family_by_default(self):
    self.assertEqual(self.listed(), {'Eric'})

  def test_filters(self):
    self.assertEqual(self.listed('?family_connection=possibly_family'), {'Cornelis'})
    self.assertEqual(self.listed('?family_connection=outsider'), {'Schrijver'})
    self.assertEqual(self.listed('?family_connection='), {'Eric', 'Cornelis', 'Schrijver'})

  def test_live_search_keeps_the_filter(self):
    # The search form sends family_connection along to the list API.
    data = self.client.get('/api/person/', {'q': 'e', 'family_connection': 'outsider'}).json()
    self.assertEqual(data['count'], 1)
    self.assertIn(self.author.get_absolute_url(), data['html'])   # (the name itself is split by search highlighting)

  def test_unknown_value_is_reported_not_silently_empty(self):
    data = self.client.get('/api/person/', {'family_connection': 'cousins'}).json()
    self.assertEqual(data['errors'], {'invalid_filters': ['family_connection']})
    self.assertEqual(data['count'], 3)   # ignored, not "nobody"

  def test_person_page_labels(self):
    self.assertNotIn('person-connection-pill', self.client.get(self.eric.get_absolute_url()).content.decode())
    self.assertContains(self.client.get(self.cornelis.get_absolute_url()), 'Possibly family')
    self.assertContains(self.client.get(self.author.get_absolute_url()), 'Outsider')

  def test_outsider_has_no_relationships_section(self):
    PersonRelation.objects.create(person_from=self.eric, person_to=self.cornelis, relation_type=PersonRelation.RelationType.PARENT)
    self.assertContains(self.client.get(self.cornelis.get_absolute_url()), 'Relationships')
    self.assertNotContains(self.client.get(self.author.get_absolute_url()), 'Relationships')
