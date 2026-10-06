from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from events.models import Event
from people.models import Person, PersonRelation
from people.timeline import age_at, life_timeline


class TimelineTests(TestCase):
  """A person's life (people/timeline.py): their own events and their close
  family's within their life, each with their age then."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='viewer')
    self.user.save()
    make = lambda given, gender='x', **f: Person.objects.create(given_name=given, last_name='Bake', gender=gender, user=self.user, status='p', visibility='c', **f)
    self.willem = make('Willem', 'm')
    self.father = make('Herman', 'm')
    self.wife = make('Jacoba', 'f')
    self.son = make('Bob', 'm')
    self.hidden_daughter = Person.objects.create(given_name='Verborgen', gender='f', user=get_user_model().objects.create(username='other'), status='p', visibility='q')
    R = PersonRelation.RelationType
    PersonRelation.objects.create(person_from=self.father, person_to=self.willem, relation_type=R.PARENT)
    PersonRelation.objects.create(person_from=self.willem, person_to=self.wife, relation_type=R.PARTNER)
    PersonRelation.objects.create(person_from=self.willem, person_to=self.son, relation_type=R.PARENT)
    PersonRelation.objects.create(person_from=self.willem, person_to=self.hidden_daughter, relation_type=R.PARENT)
    self.birth = self.event('birth', [self.willem], 1884, 4, 16)
    self.event('death', [self.willem], 1932, 10, 6)
    self.event('marriage', [self.willem, self.wife], 1909, 12, 22)
    self.event('death', [self.father], 1898, 8, 24)
    self.event('birth', [self.father], 1859)                   # before Willem's life: left out
    self.event('birth', [self.son], 1910, 9, 23)
    self.event('death', [self.son], 1944)                      # after Willem's death: left out
    self.event('birth', [self.hidden_daughter], 1912)          # a hidden person: left out
    self.event('death', [self.wife], 1930)                     # a partner's death in his life
    self.event('historical', [], 1929)                            # history in his life
    self.event('historical', [], 1942)                            # after his death: left out

  def event(self, kind, people, year, month=None, day=None):
    event = Event.objects.create(kind=kind, year=year, month=month, day=day, user=self.user)
    event.people.set(people)
    return event

  def timeline(self):
    request = RequestFactory().get('/')
    request.user = self.user
    return life_timeline(self.willem, request)

  def test_own_and_family_events_in_order(self):
    rows = [(e.event.year, e.event.kind, e.relation) for e in self.timeline()]
    self.assertEqual(rows, [
      (1884, 'birth', ''), (1898, 'death', 'father'), (1909, 'marriage', ''), (1910, 'birth', 'son'),
      (1929, 'historical', ''), (1930, 'death', 'wife'), (1932, 'death', ''),
    ])
    self.assertTrue(next(e for e in self.timeline() if e.event.kind == 'historical').history)

  def test_others_leave_out_the_person(self):
    marriage = next(e for e in self.timeline() if e.event.kind == 'marriage')
    self.assertEqual(marriage.others, [self.wife])

  def test_ages(self):
    ages = {e.event.year: e.age for e in self.timeline()}
    self.assertEqual(ages[1884], '')                            # his own birth
    self.assertEqual(ages[1898], 'aged 14')                     # 24-8 after 16-4: complete dates
    self.assertEqual(ages[1930], 'about 46')                    # a year only: about
    early = Event(kind='other', kind_freetext='x', year=1900, month=1, day=1)
    self.assertEqual(age_at(self.birth, early), 'aged 15')      # before his birthday that year

  def test_undated_birth_first_death_last_others_left_out(self):
    from people.models import Person
    person = Person.objects.create(given_name='Onbekend', user=self.user, status='p', visibility='c')
    for fields in ({'kind': 'death'}, {'kind': 'other', 'kind_freetext': 'Iets'}, {'kind': 'migration', 'year': 1920}, {'kind': 'birth'}):
      Event.objects.create(user=self.user, **fields).people.set([person])
    request = RequestFactory().get('/')
    request.user = self.user
    kinds = [entry.event.kind for entry in life_timeline(person, request)]
    self.assertEqual(kinds, ['birth', 'migration', 'death'])          # an undated 'other': no place in time
    self.assertEqual(person.count_visible_events(), 3)

  def test_no_age_from_a_before_or_after_date(self):
    circa = Event(kind='birth', year=1884, date_qualifier='circa')
    before = Event(kind='birth', year=1884, date_qualifier='before')
    wedding = Event(kind='marriage', year=1909)
    self.assertEqual(age_at(circa, wedding), 'about 25')            # circa: an estimate
    self.assertEqual(age_at(before, wedding), '')                    # before: could be years off
    self.assertEqual(age_at(self.birth, Event(kind='marriage', year=1909, date_qualifier='after')), '')

  def test_age_at_death_on_the_death_row(self):
    from people.templatetags.tags import age_at_death
    self.assertEqual(age_at_death(self.willem), 'aged 48')          # 6-10-1932 from 16-4-1884
    self.assertEqual(age_at_death(self.son), 'about 34')           # died 1944, a year only
    self.assertEqual(age_at_death(self.wife), '')                  # no birth recorded
    self.assertEqual(age_at_death(self.hidden_daughter), '')       # no death recorded
    self.son.death.__class__.objects.filter(pk=self.son.death.pk).update(date_qualifier='before')
    self.assertEqual(age_at_death(self.son), '')                   # before: could be years off
    self.client.force_login(self.user)
    html = self.client.get(self.willem.page_url()).content.decode()          # the left column's death row
    self.assertIn('(aged 48)', html)

  def test_spouse_age_at_marriage(self):
    self.event('birth', [self.wife], 1885, 5, 1)
    from django.test import Client
    client = Client()
    client.force_login(self.user)
    html = client.get(f'/api/person/{self.willem.token}/get_visible_events/').json()['fields']['get_visible_events']
    self.assertIn('aged 24</span>', html.replace('"', ''))         # Jacoba at the 1909 wedding

  def test_on_the_page(self):
    from django.test import Client
    client = Client()
    client.force_login(self.user)
    html = client.get(f'/api/person/{self.willem.token}/get_visible_events/').json()['fields']['get_visible_events']
    self.assertIn('class="timeline"', html.replace('class=timeline', 'class="timeline"'))
    self.assertIn('father', html)
    self.assertNotIn('Verborgen', html)
