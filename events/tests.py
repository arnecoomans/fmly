from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import RequestFactory, TestCase

from events.models import Event
from people.models import Person


class DateQualifierTests(TestCase):
  """PartialDateMixin.date_qualifier - exact / circa / before / after."""

  def event(self, **fields):
    user, _ = get_user_model().objects.get_or_create(username='owner')
    return Event.objects.create(kind=Event.Kind.BIRTH, user=user, **fields)

  def test_display(self):
    cases = [
      (dict(year=1968, month=7, day=5), '5 Jul 1968'),
      (dict(year=1968, month=7), 'Jul 1968'),
      (dict(year=1968), '1968'),
      (dict(year=1950, date_qualifier='circa'), 'ca. 1950'),
      (dict(year=1950, month=3, date_qualifier='before'), 'before Mar 1950'),
      (dict(year=1943, date_qualifier='after'), 'after 1943'),
      (dict(), ''),
    ]
    for fields, expected in cases:
      self.assertEqual(self.event(**fields).partial_date_display(), expected, fields)

  def test_weekday_only_for_exact_complete_dates(self):
    self.assertIsNotNone(self.event(year=1943, month=1, day=6).calendar_date())
    self.assertIsNone(self.event(year=1943, month=1, day=6, date_qualifier='circa').calendar_date())
    self.assertIsNone(self.event(year=1943, month=1).calendar_date())

  def test_person_page_shows_year_only_and_qualified_birth(self):
    user = get_user_model().objects.create(username='viewer')
    person = Person.objects.create(given_name='Pieter', user=user, status='p', visibility='p')
    birth = self.event(year=1880, date_qualifier='circa')
    birth.people.add(person)
    html = self.client.get(person.get_absolute_url()).content.decode()
    self.assertIn('ca. 1880', html)


class LifespanQualifierTests(TestCase):
  def test_lifespan_shows_qualifiers(self):
    from django.template.loader import render_to_string
    from django.test import RequestFactory
    user = get_user_model().objects.create(username='viewer')
    person = Person.objects.create(given_name='Pieter', user=user, status='p', visibility='p')
    for kind, year, qualifier in ((Event.Kind.BIRTH, 1880, 'circa'), (Event.Kind.DEATH, 1918, 'after')):
      Event.objects.create(kind=kind, year=year, date_qualifier=qualifier, user=user).people.add(person)
    request = RequestFactory().get('/')
    request.user = user
    html = render_to_string('person/functions/get_full_name.html', {'person': person, 'lifespan': True, 'request': request})
    self.assertIn('(ca. 1880–after 1918)', ' '.join(html.split()))


class EventVisibilityTests(TestCase):
  """Events have no visibility of their own: visible when at least one of
  their people is visible to the viewer (or they have no people), with the
  people the viewer may not see obfuscated (Event.display_for) - in the
  API, its search, and on person pages."""

  def setUp(self):
    from django.contrib.auth import get_user_model
    from people.models import Person
    self.member = get_user_model().objects.create(username='member')
    self.member.save()
    self.other = get_user_model().objects.create(username='other')
    self.eric = Person.objects.create(given_name='Eric', last_name='Coomans', user=self.member, status='p', visibility='p')
    self.secret = Person.objects.create(given_name='Geheime', last_name='Partner', user=self.other, status='p', visibility='q')
    self.marriage = Event.objects.create(kind=Event.Kind.MARRIAGE, year=1968, user=self.member)
    self.marriage.people.add(self.eric, self.secret)
    self.hidden = Event.objects.create(kind=Event.Kind.BIRTH, year=1950, user=self.other)
    self.hidden.people.add(self.secret)
    self.general = Event.objects.create(kind=Event.Kind.HISTORICAL, title='Opening Suezkanaal', year=1869, user=self.member)

  def api(self, url, client=None):
    from django.test import Client
    return (client or Client()).get(url).json()

  def test_visible_when_one_person_is_and_hidden_people_obfuscated(self):
    data = self.api('/api/event/')
    names = [r['name'] for r in data['results']]
    self.assertEqual(data['count'], 2)                               # marriage + general, not the hidden birth
    self.assertIn('marriage of Eric Coomans, G… P… (1968)', names)
    self.assertNotIn('Geheime', ' '.join(names))
    summary = self.api(f'/api/event/{self.marriage.token}/summary/')
    self.assertNotIn('Geheime', str(summary))

  def test_hidden_event_404s(self):
    from django.test import Client
    self.assertEqual(Client().get(f'/api/event/{self.hidden.token}/summary/').status_code, 404)

  def test_search_by_visible_names_only(self):
    self.assertEqual(self.api('/api/event/?q=eric')['count'], 1)
    self.assertEqual(self.api('/api/event/?q=geheime')['count'], 0)  # a hidden name finds nothing
    self.assertEqual(self.api('/api/event/?q=1869')['count'], 1)

  def test_person_page_obfuscates_the_hidden_spouse(self):
    from django.test import Client
    html = Client().get(self.eric.get_absolute_url()).content.decode()
    self.assertIn('G… P…', html)
    self.assertNotIn('Geheime', html)


class EventOverviewTests(TestCase):
  """/events/ (EventListView): historical by default, by decade; ?kind= for
  another kind or all; only what the viewer may see."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='viewer')
    self.user.save()
    from people.models import Person
    self.shown = Person.objects.create(given_name='Corry', user=self.user, status='p', visibility='c')
    self.hidden = Person.objects.create(given_name='Verborgen', user=get_user_model().objects.create(username='other'), status='p', visibility='q')
    Event.objects.create(kind=Event.Kind.HISTORICAL, title='Inval Japan', year=1942, user=self.user)
    Event.objects.create(kind=Event.Kind.HISTORICAL, title='Opening Suezkanaal', year=1869, user=self.user)
    Event.objects.create(kind=Event.Kind.BIRTH, year=1917, user=self.user).people.add(self.shown)
    Event.objects.create(kind=Event.Kind.BIRTH, year=1920, user=self.user).people.add(self.hidden)
    self.client.force_login(self.user)

  def html(self, query=''):
    return self.client.get(f'/events/{query}').content.decode()

  def test_historical_by_decade(self):
    html = self.html()
    self.assertLess(html.index('1860s'), html.index('1940s'))
    self.assertIn('Inval Japan', html)
    self.assertNotIn('Corry', html)                            # a birth: not historical

  def test_all_and_kinds(self):
    self.assertIn('Corry', self.html('?kind=all'))
    self.assertNotIn('Verborgen', self.html('?kind=all'))      # a hidden person's birth isn't there at all
    births = self.html('?kind=birth')
    self.assertIn('Corry', births)
    self.assertNotIn('Inval Japan', births)
    self.assertIn('Inval Japan', self.html('?kind=nonsense'))  # unknown: the default

  def test_pill_counts_are_events(self):
    marriage = Event.objects.create(kind=Event.Kind.MARRIAGE, year=1941, user=self.user)
    from people.models import Person
    marriage.people.add(self.shown, Person.objects.create(given_name='Eddie', user=self.user, status='p', visibility='c'))
    html = self.html().replace('"', '')
    self.assertIn('Marriages 1</a>', html)                     # two people, one event
    self.assertIn('Historical 2</a>', html)

  def test_divorce(self):
    """A divorce is an event of both people: in the list with its own pill
    and symbol, and in each of their timelines - why a partner is gone
    while still alive."""
    from people.models import Person
    from people.timeline import life_timeline
    eddie = Person.objects.create(given_name='Eddie', user=self.user, status='p', visibility='c')
    divorce = Event.objects.create(kind=Event.Kind.DIVORCE, year=1934, month=10, user=self.user)
    divorce.people.add(self.shown, eddie)
    html = self.html('?kind=divorce').replace('"', '')
    self.assertIn('Divorces 1</a>', html)
    self.assertIn('⚮', html)
    self.assertIn('Corry', html)
    request = RequestFactory().get('/')
    request.user = self.user
    for person in (self.shown, eddie):
      self.assertIn(divorce, [entry.event for entry in life_timeline(person, request)])

  def test_in_the_menu(self):
    self.assertIn('href="/events/"', self.html().replace('href=/events/', 'href="/events/"'))


class EventEditingTests(TestCase):
  """An event's page and editing (Event.api_edit_forms, relations, the
  create dialog), and deleting as a status."""

  def setUp(self):
    from django.contrib.auth.models import Permission
    from django.test import Client
    from people.models import Person
    self.editor = get_user_model().objects.create(username='editor')
    for codename in ('add_event', 'change_event', 'delete_event', 'change_person'):
      self.editor.user_permissions.add(Permission.objects.get(codename=codename))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.person = Person.objects.create(given_name='Corry', user=self.editor, status='p', visibility='c')
    self.birth = Event.objects.create(kind=Event.Kind.BIRTH, year=1917, user=self.editor)
    self.birth.people.add(self.person)
    self.history = Event.objects.create(kind=Event.Kind.HISTORICAL, title='Inval Japan', year=1942, user=self.editor)

  def save(self, event, block, **fields):
    event.refresh_from_db()
    data = {'_modified': event.date_modified.isoformat(), **{f'{block}-{k}': v for k, v in fields.items()}}
    return self.client.post(f'/api/event/{event.token}/form/{block}/', data)

  def test_page(self):
    from django.test import Client
    html = self.client.get(self.history.get_absolute_url()).content.decode().replace('"', '')
    for block in ('what', 'date', 'description', 'status'):
      self.assertIn(f'data-cmnsd-edit-name={block} ', html)
    self.assertEqual(Client().get(self.history.get_absolute_url()).status_code, 200)   # historical: public
    self.assertEqual(Client().get(self.birth.get_absolute_url()).status_code, 404)     # through a signed-in-only person

  def test_cards_link_to_the_page(self):
    html = self.client.get('/events/').content.decode().replace('"', '')
    self.assertIn(f'href={self.history.get_absolute_url()}>Inval Japan</a>', html)

  def test_what_needs_a_label_for_other(self):
    self.assertEqual(self.save(self.history, 'what', kind='other', title='', kind_freetext='').status_code, 400)
    self.assertEqual(self.save(self.history, 'what', kind='other', title='', kind_freetext='Bezetting').status_code, 200)
    self.assertEqual(Event.objects.get(pk=self.history.pk).label(), 'Bezetting')

  def test_create_with_a_person(self):
    response = self.client.post('/api/event/new/', {
      'kind': 'marriage', 'date_qualifier': 'exact', 'year': '1941', 'month': '3', 'day': '12', 'person': self.person.token,
    })
    self.assertEqual(response.status_code, 200)
    event = Event.objects.get(kind='marriage')
    self.assertEqual((list(event.people.all()), event.status), ([self.person], 'p'))
    self.assertEqual(response.json()['created']['url'], event.get_absolute_url())

  def family(self):
    """Corry's wife and son, and an outsider - with their relations."""
    from people.models import Person, PersonRelation
    make = lambda name, gender: Person.objects.create(given_name=name, gender=gender, user=self.editor, status='p', visibility='c')
    wife, son, other = make('Jacoba', 'f'), make('Bob', 'm'), make('Willem', 'm')
    PersonRelation.objects.create(person_from=self.person, person_to=wife, relation_type='partner')
    PersonRelation.objects.create(person_from=self.person, person_to=son, relation_type='parent')
    return wife, son, other

  def new(self, **fields):
    data = {'kind': 'other', 'kind_freetext': 'Feest', 'date_qualifier': 'exact', 'year': '1950', 'person': self.person.token, **fields}
    return self.client.post('/api/event/new/', data)

  def test_create_offers_the_family_and_anyone(self):
    wife, son, _other = self.family()
    html = self.client.get(f'/api/event/new/?person={self.person.token}').json()['html'].replace('"', '')
    self.assertLess(html.index('Jacoba'), html.index('Bob'))                    # partners first
    self.assertIn('(wife)', html)
    self.assertIn('(son)', html)
    self.assertIn('data-cmnsd-picker=person', html)                            # someone else
    self.assertIn('event-form__partner-hint', html)
    html = self.client.get('/api/event/new/').json()['html'].replace('"', '')   # from the events page: the picker only
    self.assertNotIn('toggle-choices', html)
    self.assertIn('data-cmnsd-picker=person', html)

  def test_create_with_people(self):
    wife, son, other = self.family()
    self.assertEqual(self.new(with_people=[wife.token, son.token], other_person=other.token).status_code, 200)
    event = Event.objects.get(kind_freetext='Feest')
    self.assertEqual(set(event.people.all()), {self.person, wife, son, other})
    self.assertNotIn(other, self.person.get_partners())                         # not a marriage: no partner link

  def test_marriage_links_a_new_partner(self):
    wife, son, other = self.family()
    self.new(kind='marriage', kind_freetext='', other_person=other.token)       # a first marriage, not linked yet
    self.assertEqual(set(Event.objects.get(kind='marriage').people.all()), {self.person, other})
    self.assertEqual(set(self.person.get_partners()), {wife, other})
    self.new(kind='divorce', kind_freetext='', with_people=[wife.token])        # already a partner: nothing to link
    self.assertEqual(len(self.person.get_partners()), 2)

  def test_a_refused_partner_link_keeps_the_event(self):
    wife, son, other = self.family()
    response = self.new(kind='marriage', kind_freetext='', with_people=[son.token])   # a child can't be a partner
    self.assertEqual(response.status_code, 200)
    self.assertEqual(set(Event.objects.get(kind='marriage').people.all()), {self.person, son})
    self.assertNotIn(son, self.person.get_partners())
    self.assertIn("wasn't linked as a partner", ' '.join(m['text'] for m in response.json()['messages']))

  def test_link_people_places_content(self):
    import json
    from content.models import Content
    item = Content.objects.create(name='Akte', kind='document', user=self.editor, status='p', visibility='c')
    post = lambda relation, **data: self.client.post(f'/api/event/{self.history.token}/link/', json.dumps({'relation': relation, **data}), content_type='application/json')
    self.assertEqual(post('people', token=self.person.token).status_code, 200)
    self.assertEqual(post('content', token=item.token).status_code, 200)
    self.assertIn(self.history, item.events.all())

  def test_deleted_is_gone_everywhere(self):
    self.save(self.birth, 'status', status='x')
    self.assertEqual(Event.objects.get(pk=self.birth.pk).status, 'x')
    self.assertIsNone(self.person.birth)                                    # not her birth any more
    self.assertEqual(self.client.get(self.birth.get_absolute_url()).status_code, 404)
    self.assertNotIn(self.birth.get_absolute_url(), self.client.get('/events/?kind=all').content.decode())


class EventPlacePickerTests(TestCase):
  """The place picker in the event dialog: a visible field (once), and a
  typed name makes a new place - or uses the one place of that name."""

  def setUp(self):
    from django.contrib.auth.models import Permission
    from django.test import Client
    self.user = get_user_model().objects.create(username='editor')
    for codename in ('add_event', 'add_place'):
      self.user.user_permissions.add(Permission.objects.get(codename=codename))
    self.user.save()
    self.client = Client()
    self.client.force_login(self.user)

  def create(self, **fields):
    data = {'kind': 'historical', 'title': 'Test', 'date_qualifier': 'exact', 'year': '1945', **fields}
    return self.client.post('/api/event/new/', data)

  def test_the_picker_is_shown_once_with_its_label(self):
    html = self.client.get('/api/event/new/').json()['html'].replace('"', '')
    self.assertEqual(html.count('data-cmnsd-picker=place'), 1)
    self.assertIn('data-picker-create=', html)

  def test_a_typed_name_makes_a_place(self):
    from places.models import Place
    self.assertEqual(self.create(**{'place__new': 'Semarang'}).status_code, 200)
    place = Place.objects.get(name='Semarang')
    self.assertEqual(list(Event.objects.get(title='Test').places.all()), [place])

  def test_an_existing_name_is_used_and_two_are_refused(self):
    from places.models import Place
    batavia = Place.objects.create(name='Batavia', user=self.user)
    self.create(**{'place__new': 'batavia'})
    self.assertEqual(Place.objects.filter(name__iexact='batavia').count(), 1)
    self.assertEqual(list(Event.objects.get(title='Test').places.all()), [batavia])
    Place.objects.create(name='Java', user=self.user)
    Place.objects.create(name='Java', user=self.user)
    self.assertEqual(self.create(title='Twee', **{'place__new': 'Java'}).status_code, 400)


class CalendarTests(TestCase):
  """events/calendar/ and events/anniversaries.py: a month of events by day -
  living people's birthdays for signed-in viewers only."""

  def setUp(self):
    from people.models import Person
    self.user = get_user_model().objects.create(username='viewer')
    self.user.save()
    self.client.force_login(self.user)
    self.deceased = Person.objects.create(given_name='Willem', user=self.user, status='p', visibility='c')
    self.living = Person.objects.create(given_name='Levend', user=self.user, status='p', visibility='c')
    self.make('death', self.deceased, 1932, 10, 6)
    self.make('birth', self.deceased, 1884, 10, 16)
    self.make('birth', self.living, 1990, 10, 16)
    self.make('marriage', self.deceased, 1909, 12, 30)

  def make(self, kind, person, year, month, day):
    event = Event.objects.create(kind=kind, year=year, month=month, day=day, user=self.user)
    event.people.add(person)
    return event

  def test_a_month_by_day(self):
    html = self.client.get('/events/calendar/?month=10').content.decode().replace('"', '')
    self.assertLess(html.index('id=day-6'), html.index('id=day-16'))
    self.assertIn('Willem', html)
    self.assertIn('Levend', html)                                          # signed in: a living person's birthday too
    from django.test import Client
    self.assertNotIn('Levend', Client().get('/events/calendar/?month=10').content.decode())   # signed out: not

  def test_coming_week_runs_into_january(self):
    from datetime import date, timedelta
    from django.test import RequestFactory
    from events.anniversaries import anniversaries
    request = RequestFactory().get('/')
    request.user = self.user
    january = self.make('death', self.deceased, 1933, 1, 2)
    days = [date(2026, 12, 29) + timedelta(days=n) for n in range(7)]
    events = anniversaries(request, days=days)
    self.assertEqual([(e.month, e.day) for e in events], [(12, 30), (1, 2)])
    self.assertIn(january, events)

  def test_bad_month_is_this_month(self):
    self.assertEqual(self.client.get('/events/calendar/?month=13').status_code, 200)
    self.assertEqual(self.client.get('/events/calendar/?month=x').status_code, 200)


class EventCommentTests(TestCase):
  """Comments on an event (CommentableMixin): on its page, in the comment
  list - named as the viewer may see it."""

  def test_comment_on_an_event(self):
    import json
    from people.models import Person
    from core.models import Comment
    user = get_user_model().objects.create(username='member')
    user.user_permissions.add(Permission.objects.get(codename='add_comment'))
    user.save()
    self.client.force_login(user)
    hidden = Person.objects.create(given_name='Verborgen', last_name='Persoon', user=get_user_model().objects.create(username='x'), status='p', visibility='q')
    shown = Person.objects.create(given_name='Corry', user=user, status='p', visibility='c')
    marriage = Event.objects.create(kind=Event.Kind.MARRIAGE, year=1941, user=user)
    marriage.people.add(shown, hidden)
    response = self.client.post(f'/api/event/{marriage.token}/add_comment/', json.dumps({'content': 'Mooie dag'}), content_type='application/json')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(Comment.objects.get().target, marriage)
    self.assertContains(self.client.get(marriage.get_absolute_url()), 'Mooie dag')
    listing = self.client.get('/comments/').content.decode()
    self.assertIn('Mooie dag', listing)
    self.assertNotIn('Verborgen', listing)                                 # the event named as this viewer may see it
    self.assertNotIn('Verborgen', self.client.get('/').content.decode())  # the dashboard's conversation too
