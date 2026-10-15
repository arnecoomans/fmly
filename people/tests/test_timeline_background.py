import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory, TestCase

from cmnsd.edit.mode import SESSION_KEY
from cmnsd.ui.state import set_sort
from events.models import Event
from people.models import Person
from people.timeline import life_timeline


class BackgroundTests(TestCase):
  """History on the timeline (issue #464): background events, history that
  participants don't hide from others, and the show/hide switch.

  Homer is in A, A is background for B, Maggie is in B."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='viewer')
    self.user.save()
    make = lambda given: Person.objects.create(given_name=given, last_name='Simpson', user=self.user, status='p', visibility='c')
    self.homer, self.maggie, self.bart = make('Homer'), make('Maggie'), make('Bart')
    for person, year in ((self.homer, 1900), (self.maggie, 1930), (self.bart, 1925)):
      self.event('birth', [person], year)
    self.a = self.event('historical', [self.homer], 1950, 1, 18, title='Sibajak vrijgegeven')
    self.b = self.event('migration', [self.maggie], 1950, 3, 16, title='Aankomst per Sibajak')
    self.a.background_for.add(self.b)

  def event(self, kind, people, year, month=None, day=None, **fields):
    event = Event.objects.create(kind=kind, year=year, month=month, day=day, user=self.user, **fields)
    event.people.set(people)
    return event

  def timeline(self, person):
    request = RequestFactory().get('/')
    request.user = self.user
    request.session = {}
    return life_timeline(person, request)

  def rows(self, person):
    return {entry.event.title: ('background' if entry.background else 'history' if entry.history else 'own') for entry in self.timeline(person) if entry.event.title}

  # --- who sees what ---

  def test_homer_maggie_table(self):
    self.assertEqual(self.rows(self.homer), {'Sibajak vrijgegeven': 'own'})          # not B: one way
    self.assertEqual(self.rows(self.maggie), {'Sibajak vrijgegeven': 'background', 'Aankomst per Sibajak': 'own'})
    self.assertEqual(self.rows(self.bart), {})                                       # linked: specific, not general history

  def test_background_says_what_it_explains_and_comes_first(self):
    entries = [e for e in self.timeline(self.maggie) if e.event.title]
    self.assertEqual([e.event.title for e in entries], ['Sibajak vrijgegeven', 'Aankomst per Sibajak'])
    self.assertEqual(entries[0].explains, [self.b])

  def test_one_step(self):
    c = self.event('historical', [], 1949, title='Soevereiniteitsoverdracht')
    c.background_for.add(self.a)   # background for A, A background for B
    self.assertNotIn('Soevereiniteitsoverdracht', self.rows(self.maggie))
    self.assertEqual(self.rows(self.homer).get('Soevereiniteitsoverdracht'), 'background')

  def test_no_doubles(self):
    self.b.people.add(self.homer)
    self.assertEqual(self.rows(self.homer), {'Sibajak vrijgegeven': 'own', 'Aankomst per Sibajak': 'own'})

  def test_background_also_before_birth(self):
    old = self.event('historical', [], 1869, title='Opening Suezkanaal')
    old.background_for.add(self.b)
    titles = [e.event.title for e in self.timeline(self.maggie) if e.event.title]
    self.assertEqual(titles[0], 'Opening Suezkanaal')   # before her birth (1930), first

  def test_undated_background_goes_with_what_it_explains(self):
    undated = self.event('historical', [], None, title='Ongedateerd')
    undated.background_for.add(self.b)
    titles = [e.event.title for e in self.timeline(self.maggie) if e.event.title]
    self.assertEqual(titles, ['Sibajak vrijgegeven', 'Ongedateerd', 'Aankomst per Sibajak'])

  # --- general history ---

  def test_participants_dont_hide_history_from_others(self):
    self.event('historical', [self.homer], 1942, title='Inval Japan')
    self.assertEqual(self.rows(self.homer).get('Inval Japan'), 'own')
    self.assertEqual(self.rows(self.bart).get('Inval Japan'), 'history')
    self.assertEqual(self.rows(self.maggie).get('Inval Japan'), 'history')

  def test_history_without_people_still_for_everyone(self):
    self.event('historical', [], 1945, title='Overgave Japan')
    self.assertEqual(self.rows(self.bart).get('Overgave Japan'), 'history')

  # --- linking ---

  def test_not_its_own_background(self):
    self.a.background_for.add(self.a)   # the admin, a script: dropped quietly
    self.assertEqual(list(self.a.background_for.all()), [self.b])

  def editor_client(self):
    editor = get_user_model().objects.create(username='editor')
    for codename in ('change_event', 'add_event'):
      editor.user_permissions.add(Permission.objects.get(codename=codename))
    editor.save()
    client = Client()
    client.force_login(editor)
    return client

  def link_background(self, client, event, token):
    return client.post(f'/api/event/{event.token}/link/', json.dumps({'relation': 'background', 'token': token}), content_type='application/json')

  def test_background_is_linked_from_the_event_with_people(self):
    client = self.editor_client()
    c = self.event('historical', [], 1949, title='Soevereiniteitsoverdracht')
    response = self.link_background(client, self.b, c.token)
    self.assertEqual(response.status_code, 200)
    self.assertIn('Soevereiniteitsoverdracht', response.json()['html'])
    self.assertEqual(set(self.b.background.all()), {self.a, c})
    self.assertEqual(self.link_background(client, self.b, self.b.token).status_code, 400)   # itself

  def test_no_background_for_an_event_without_people(self):
    client = self.editor_client()
    surrender = self.event('historical', [], 1945, 8, 15, title='Overgave Japan')
    bomb = self.event('historical', [], 1945, 8, 6, title='Hiroshima')
    self.assertEqual(self.link_background(client, surrender, bomb.token).status_code, 400)
    self.assertFalse(surrender.background.exists())

  def test_event_page_edits_background_only_with_people(self):
    client = self.editor_client()
    session = client.session
    session[SESSION_KEY] = True
    session.save()
    with_people = client.get(self.b.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('Sibajak vrijgegeven', with_people)   # its background, listed
    self.assertIn('relation type=hidden value=background', with_people.replace('name=relation ', 'relation '))
    self.assertIn('/new/?kind=historical', with_people)   # "+ new historical event"
    lonely = self.event('historical', [], 1945, title='Overgave Japan')   # without people: no picker
    page = client.get(lonely.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('/new/?kind=historical', page)   # (the breadcrumb has ?kind= too)
    self.assertIn('Aankomst per Sibajak', client.get(self.a.get_absolute_url()).content.decode())   # A: "background for", read only

  # --- background for an event without people changes nothing ---

  def test_hiroshima_for_the_surrender_stays_history(self):
    surrender = self.event('historical', [], 1945, 8, 15, title='Overgave Japan')
    bomb = self.event('historical', [], 1945, 8, 6, title='Hiroshima')
    bomb.background_for.add(surrender)   # the admin, a script: allowed, but no effect on timelines
    self.assertEqual(self.rows(self.bart).get('Hiroshima'), 'history')
    self.assertEqual(self.rows(self.bart).get('Overgave Japan'), 'history')

  def test_arrival_without_people_releases_its_background(self):
    self.b.people.clear()
    self.assertEqual(self.rows(self.bart).get('Sibajak vrijgegeven'), 'history')

  # --- the switch ---

  def test_switch_only_with_history_and_remembered(self):
    client = Client()
    client.force_login(self.user)
    # Maggie's timeline has only her own and background: no switch.
    maggie = client.get(f'/api/person/{self.maggie.token}/get_visible_events/', HTTP_ACCEPT='application/json').json()['fields']['get_visible_events']
    self.assertNotIn('person.history', maggie)
    self.event('historical', [], 1945, title='Overgave Japan')
    url = f'/api/person/{self.bart.token}/get_visible_events/'
    html = client.get(url, HTTP_ACCEPT='application/json').json()['fields']['get_visible_events'].replace('"', '')
    self.assertIn('data-cmnsd-filter-save=person.history', html)
    self.assertRegex(html, r'content-grid-pill is-active[^>]*data-filter[ >]')   # default: with history
    request = RequestFactory().get('/')
    request.user = self.user
    set_sort(request, 'person.history', 'life')
    html = client.get(url, HTTP_ACCEPT='application/json').json()['fields']['get_visible_events'].replace('"', '')
    self.assertRegex(html, r'content-grid-pill is-active[^>]*data-filter=life')


class ResidenceTests(TestCase):
  """A residence event (issue #465): proof someone lived somewhere, from a
  source outside the archive - their own event, like any other."""

  def test_residence_is_an_own_event(self):
    user = get_user_model().objects.create(username='viewer')
    user.save()
    lisa = Person.objects.create(given_name='Lisa', user=user, status='p', visibility='c')
    Event.objects.create(kind='birth', year=1920, user=user).people.set([lisa])
    residence = Event.objects.create(kind='residence', year=1935, user=user, description='Adresboek Amsterdam 1935')
    residence.people.set([lisa])
    request = RequestFactory().get('/')
    request.user = user
    entry = next(e for e in life_timeline(lisa, request) if e.event == residence)
    self.assertFalse(entry.history or entry.background)
    self.assertEqual(entry.age, 'about 15')
