from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from events.models import Event
from people.models import Person


class InitialsSearchTests(TestCase):
  """A search word written as initials (people/names.py initials_pattern):
  "P.W.A." and "p. w. a." from the first given name, "pwa" for exactly
  these given names, "Ch." a two-letter one - in the people search, and
  for an event's people."""

  def setUp(self):
    self.me = get_user_model().objects.create(username='zoeker')
    self.me.save()
    self.client = Client()
    self.client.force_login(self.me)
    person = lambda given, last='Coomans': Person.objects.create(given_name=given, last_name=last, user=self.me, status='p', visibility='c')
    self.piet = person('Pieter Willem Anthonie')
    self.four = person('Pieter Willem Anthonie Johannes')
    self.abraham = person('Abraham')
    self.christiaan = person('Christiaan Cornelis', 'Bake')
    self.typed = person('P.W.A.', 'Stapel')                            # known by initials only

  def found(self, query):
    from cmnsd.api.filtering import build_list
    from django.http import QueryDict
    from django.test import RequestFactory
    request = RequestFactory().get('/')
    request.user = self.me
    params = QueryDict(mutable=True)
    params['q'] = query
    return set(build_list(Person, request, params=params)['objects'])

  def test_with_dots_from_the_first_given_name(self):
    for query in ('P.W.A.', 'p.w.a.', 'P.W.'):
      self.assertEqual(self.found(query), {self.piet, self.four, self.typed}, query)
    self.assertEqual(self.found('W.A.'), {self.typed})                    # in order, from the first - "P.W.A." holds the text
    self.assertEqual(self.found('P.W.A. Coomans'), {self.piet, self.four})

  def test_spaced_each_starts_a_given_name(self):
    self.assertEqual(self.found('p. w. a. coomans'), {self.piet, self.four})
    self.assertEqual(self.found('A. Coomans'), {self.piet, self.four, self.abraham})

  def test_without_dots_exactly_these_given_names(self):
    self.assertEqual(self.found('pwa'), {self.piet, self.typed})
    self.assertEqual(self.found('PWAJ'), {self.four})
    self.assertEqual(self.found('pw'), set())

  def test_a_two_letter_initial(self):
    self.assertEqual(self.found('Ch.'), {self.christiaan})
    self.assertEqual(self.found('C.C.'), {self.christiaan})

  def test_a_title_is_not_initials(self):
    doctor = Person.objects.create(given_name='Dirk', last_name='Rinkes', user=self.me, status='p', visibility='c')
    self.assertNotIn(doctor, self.found('Dr.'))

  def test_an_event_by_its_peoples_initials(self):
    event = Event.objects.create(kind='marriage', year=1910, user=self.me, status='p')
    event.people.add(self.piet)
    found = self.client.get('/api/event/?q=P.W.A.&format=picker', HTTP_ACCEPT='application/json').json()
    self.assertIn(event.token, found['html'])

  def test_search_page_names_first(self):
    self.abraham.biography = 'Zoon van P.W.A.'                           # found in the text, not the name
    self.abraham.save()
    from core.search import search
    from django.test import RequestFactory
    request = RequestFactory().get('/')
    request.user = self.me
    people = [section for section in search(request, 'P.W.A. Coomans') if section.kind == 'person'][0]
    self.assertEqual(people.hits[-1], self.abraham)
    self.assertEqual(people.hits[0].search_snippet, '')                  # the initials explain the hit
