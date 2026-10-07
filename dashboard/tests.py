from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory, TestCase

from events.models import Event
from people.models import Person

from . import blocks


class DashboardTestCase(TestCase):
  def setUp(self):
    self.editor = self.user('editor', 'add_content', 'change_content', 'change_person', 'add_person', 'add_note')
    self.reader = self.user('reader')

  def user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def request(self, user):
    request = RequestFactory().get('/')
    request.user = user
    return request

  def person(self, given, **fields):
    return Person.objects.create(given_name=given, user=self.editor, status='p', visibility='c', **fields)

  def event(self, kind, people, day, year):
    event = Event.objects.create(kind=kind, year=year, month=day.month, day=day.day, user=self.editor)
    event.people.set(people)
    return event


class OnThisDayTests(DashboardTestCase):
  """What happened on today's date - a living person's birthday for a
  signed-in viewer, signed out only births of the dead; the coming week
  on a day without any."""

  def test_today(self):
    today = date(2026, 10, 3)
    deceased, living = self.person('Willem'), self.person('Levend')
    self.event('death', [deceased], date(1932, 10, 6), 1932)
    born = self.event('birth', [deceased], today, 1884)
    self.event('birth', [living], today, 1990)
    married = self.event('marriage', [deceased, living], today, 1909)
    events, label = blocks.on_this_day(self.request(self.reader), today)
    living_birth = Event.objects.get(kind='birth', people=living)
    self.assertEqual(events, [born, married, living_birth])                # by year; signed in: living birthdays too
    self.assertEqual(str(label), 'on this day')
    from django.contrib.auth.models import AnonymousUser
    from events.anniversaries import anniversaries
    signed_out = anniversaries(self.request(AnonymousUser()), days=[today])
    self.assertNotIn(living_birth, signed_out)                              # signed out: only of the dead

  def test_every_kind_with_a_day(self):
    today = date(2026, 3, 9)
    invasion = Event.objects.create(kind='historical', title='Inval Japan', year=1942, month=3, day=9, user=self.editor)
    move = self.event('migration', [self.person('Albert')], today, 1946)
    events, _label = blocks.on_this_day(self.request(self.reader), today)
    self.assertEqual(events, [invasion, move])

  def test_the_coming_week_on_an_empty_day(self):
    today = date(2026, 10, 3)
    person = self.person('Corry')
    soon = self.event('death', [person], today + timedelta(days=3), 1994)
    events, label = blocks.on_this_day(self.request(self.reader), today)
    self.assertEqual((events, str(label)), ([soon], 'this coming week'))


class DashboardPageTests(DashboardTestCase):
  def test_editor_sees_the_work_blocks(self):
    client = Client()
    client.force_login(self.editor)
    html = client.get('/').content.decode().replace('"', '')
    self.assertIn('data-cmnsd-upload=/content/new/upload/', html)          # the inbox's dropzone
    self.assertIn('data-upload-count=#dashboard-inbox-count', html)
    self.assertIn('data-upload-thumbs=#dashboard-drafts', html)                # new uploads join the strip
    self.assertIn('id=dashboard-drafts', html)                                   # there even while empty

  def test_reader_and_visitor_do_not(self):
    client = Client()
    client.force_login(self.reader)
    self.assertNotIn('data-cmnsd-upload', client.get('/').content.decode())
    visitor = Client().get('/')
    self.assertEqual(visitor.status_code, 200)
    html = visitor.content.decode()
    self.assertIn('/accounts/login/', html)                                 # a way in
    self.assertIn('/accounts/register/', html)
    self.assertNotIn('dashboard__block', html)                              # nothing advertised
    self.assertNotIn('nav-menu', html)                                      # no "more" menu
    self.assertNotIn('/events/', html)

  def test_loose_ends_are_for_editors(self):
    self.person('Zonder geboorte')
    client = Client()
    client.force_login(self.editor)
    response = client.get('/dashboard/loose-ends/no-birth/')
    self.assertContains(response, 'Zonder geboorte')
    reader = Client()
    reader.force_login(self.reader)
    self.assertEqual(reader.get('/dashboard/loose-ends/no-birth/').status_code, 404)
    self.assertEqual(client.get('/dashboard/loose-ends/nonsense/').status_code, 404)

  def test_logo_and_menu_lead_home(self):
    client = Client()
    client.force_login(self.reader)
    html = client.get('/people/').content.decode().replace('"', '')
    self.assertIn('class=app-topbar__logo href=/>', html)


class AnotherFromTheArchiveTests(DashboardTestCase):
  def test_another_answers_only_the_block(self):
    """"Another" (list.js) swaps the block in place: JSON with its html, not the page."""
    client = Client()
    client.force_login(self.reader)
    response = client.get('/', headers={'x-requested-with': 'XMLHttpRequest', 'accept': 'application/json'})
    html = response.json()['html']
    self.assertIn('data-cmnsd-target="#from-the-archive"', html)
    self.assertNotIn('<html', html)

  def test_signed_out_gets_the_welcome(self):
    response = Client().get('/', headers={'x-requested-with': 'XMLHttpRequest'})
    self.assertNotIn('from-the-archive', response.content.decode())


class LooseEndRulesTests(DashboardTestCase):
  def items(self, name):
    return list(blocks.loose_end_items(name, self.request(self.editor)).distinct())

  def test_no_birth_leaves_outsiders_out(self):
    family, possibly = self.person('Willem'), self.person('Jan', family_connection='possibly_family')
    self.person('Jeroen', family_connection='outsider')                         # an author: in the archive for his books
    born = self.person('Bob')
    self.event('birth', [born], date(1910, 9, 23), 1910)
    self.assertEqual(set(self.items('no-birth')), {family, possibly})

  def test_other_events_with_a_title_are_fine(self):
    untitled = Event.objects.create(kind='other', kind_freetext='Verhuizing', user=self.editor)
    Event.objects.create(kind='other', kind_freetext='Benoeming', title='Benoeming tot ambtenaar', user=self.editor)
    self.assertEqual(self.items('other-events'), [untitled])

  def test_open_transcripts(self):
    from content.models import Content, Transcript
    item = Content.objects.create(name='Krant', kind='document', user=self.editor, status='p', visibility='c')
    Transcript.objects.create(content=item, kind='original', language='nl', method='automatic', text='OCR')
    checked = Content.objects.create(name='Brief', kind='document', user=self.editor, status='p', visibility='c')
    Transcript.objects.create(content=checked, kind='original', language='nl', method='automatic_checked', text='OK')
    unfinished = Content.objects.create(name='Dagboek', kind='document', user=self.editor, status='p', visibility='c')
    Transcript.objects.create(content=unfinished, kind='original', language='nl', method='manual', text='Half', incomplete=True)
    self.assertEqual(self.items('open-transcripts'), [item, unfinished])            # unchecked, and incomplete


class ContentDraftsTests(DashboardTestCase):
  def test_draft_cards_are_marked_and_authors_are_outsiders(self):
    from content.models import Content
    Content.objects.create(name='Klad', kind='photo', user=self.editor, status='c', visibility='c')
    book = Content.objects.create(name='Boek', kind='book', user=self.editor, status='p', visibility='c')
    client = Client()
    client.force_login(self.editor)
    html = client.get('/content/').content.decode().replace('"', '')
    self.assertIn('content-card--draft', html)
    client.post('/ui/edit/', {'on': '1', 'next': '/'})
    page = client.get(book.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('/api/person/new/?family_connection=outsider', page)   # a new author: an outsider


class MarkedLooseEndTests(DashboardTestCase):
  """The "Loose end" tag: whatever carries it is listed under loose ends."""

  def setUp(self):
    super().setUp()
    from core.models import Tag
    from core.tags import LOOSE_END_SLUG
    self.tag = Tag.objects.get_or_create(slug=LOOSE_END_SLUG, parent=None, defaults={'name': 'Loose end', 'user': self.editor, 'status': 'p', 'visibility': 'c'})[0]

  def test_marked_people_and_content(self):
    from content.models import Content
    person = self.person('Uitzoeken')
    person.tags.add(self.tag)
    item = Content.objects.create(name='Onduidelijke foto', kind='photo', user=self.editor, status='p', visibility='c')
    item.tags.add(self.tag)
    rows = {name: count for name, _label, count in blocks.loose_ends(self.request(self.editor))}
    self.assertEqual(rows['marked'], 2)
    client = Client()
    client.force_login(self.editor)
    html = client.get('/dashboard/loose-ends/marked/').content.decode()
    self.assertIn('Uitzoeken', html)
    self.assertIn('Onduidelijke foto', html)


class InboxDraftsTests(DashboardTestCase):
  """The inbox: draft content, people and events of the user."""

  def test_draft_people_and_events_counted_and_listed(self):
    Person.objects.create(given_name='Klad', user=self.editor, status='c', visibility='c')
    Event.objects.create(kind='historical', title='Klad-gebeurtenis', status='c', user=self.editor)
    Person.objects.create(given_name='Gepubliceerd', user=self.editor, status='p', visibility='c')
    from content.views.upload import inbox_total
    self.assertEqual(inbox_total(self.editor), 2)
    client = Client()
    client.force_login(self.editor)
    html = client.get('/content/inbox/').content.decode()
    self.assertIn('Klad', html)
    self.assertIn('Klad-gebeurtenis', html)
    self.assertNotIn('Gepubliceerd', html)
    self.assertIn('2 drafts', html)


class AddPersonTests(DashboardTestCase):
  """"Add person" - in the More menu and on the people list, for those
  who may add people; their drafts in the inbox."""

  def test_menu_and_list(self):
    client = Client()
    client.force_login(self.editor)
    html = client.get('/people/').content.decode().replace('"', '')
    self.assertEqual(html.count('href=/people/new/'), 2)                    # the menu and the list
    reader = Client()
    reader.force_login(self.reader)
    self.assertNotIn('/people/new/', reader.get('/people/').content.decode())

  def test_inbox_without_add_content(self):
    genealogist = self.user('genealogist', 'add_person')
    client = Client()
    client.force_login(genealogist)
    html = client.get('/content/inbox/').content.decode().replace('"', '')
    self.assertIn('href=/content/inbox/', html)
    self.assertNotIn('href=/content/new/', html)
    reader = Client()
    reader.force_login(self.reader)
    self.assertEqual(reader.get('/content/inbox/').status_code, 403)


class YearsAgoTests(TestCase):
  """How long ago, as sure as the date: about / at least / at most."""

  def test_qualifiers(self):
    from dashboard.templatetags.dashboard import years_ago
    years = date.today().year - 1900
    self.assertEqual(years_ago(Event(kind='birth', year=1900)), f'{years} years ago')
    self.assertEqual(years_ago(Event(kind='birth', year=1900, date_qualifier='circa')), f'about {years} years ago')
    self.assertEqual(years_ago(Event(kind='birth', year=1900, date_qualifier='before')), f'at least {years} years ago')
    self.assertEqual(years_ago(Event(kind='birth', year=1900, date_qualifier='after')), f'at most {years} years ago')


class UndatedPerPersonTests(DashboardTestCase):
  """Undated events: one list, each person's together (birth first), each
  event once, events without (visible) people last."""

  def test_order(self):
    anna, bert = self.person('Anna', last_name='Aal'), self.person('Bert', last_name='Bos')
    hidden = Person.objects.create(given_name='Verborgen', last_name='Aaa', user=get_user_model().objects.create(username='x'), status='p', visibility='q')
    loose = Event.objects.create(kind='historical', title='Ergens', user=self.editor)
    death = Event.objects.create(kind='death', user=self.editor)
    death.people.set([bert])
    marriage = Event.objects.create(kind='marriage', user=self.editor)
    marriage.people.set([bert, anna, hidden])
    birth = Event.objects.create(kind='birth', user=self.editor)
    birth.people.set([bert])
    Event.objects.create(kind='birth', year=1900, user=self.editor).people.set([anna])   # dated: not here
    events = blocks.undated_by_person(Event.objects.filter(year__isnull=True), self.request(self.editor))
    self.assertEqual([e.pk for e in events], [marriage.pk, birth.pk, death.pk, loose.pk])   # Aal (not hidden Aaa), Bos, nobody
    client = Client()
    client.force_login(self.editor)
    html = client.get('/dashboard/loose-ends/undated-events/').content.decode()
    self.assertNotIn('Verborgen', html)


class LowResolutionTests(DashboardTestCase):
  """Images under LOW_RESOLUTION_PIXELS, smallest first - by total pixels,
  so a narrow clipping counts as what it is."""

  def test_smallest_first(self):
    from content.models import Content
    make = lambda name, w, h: Content.objects.create(name=name, kind='photo', user=self.editor, status='p', visibility='c', width=w, height=h)
    tiny, small = make('Klein', 200, 150), make('Smal', 1013, 198)
    make('Groot', 1200, 900)
    Content.objects.create(name='Onbekend', kind='photo', user=self.editor, status='p', visibility='c')   # not measured: not here
    self.assertEqual([c.pk for c in blocks.loose_end_items('low-resolution', self.request(self.editor))], [tiny.pk, small.pk])
    client = Client()
    client.force_login(self.editor)
    self.assertContains(client.get('/dashboard/loose-ends/low-resolution/'), '200 × 150')


class DismissalTests(DashboardTestCase):
  """"Fine as it is" (LooseEndDismissal): off one loose end - and its count
  - not the others; restorable; only an item that loose end holds."""

  def setUp(self):
    super().setUp()
    from content.models import Content
    self.clipping = Content.objects.create(name='Knipsel', kind='photo', user=self.editor, status='p', visibility='c', width=300, height=100)
    self.client = Client()
    self.client.force_login(self.editor)

  def rows(self, name):
    return {n: count for n, _label, count in blocks.loose_ends(self.request(self.editor))}.get(name, 0)

  def test_dismiss_and_restore(self):
    self.assertEqual(self.rows('low-resolution'), 1)
    self.assertEqual(self.rows('photos-without-people'), 1)
    self.client.post('/dashboard/loose-ends/low-resolution/', {'object_id': self.clipping.pk, 'note': 'Delpher, beter wordt het niet'})
    self.assertEqual(self.rows('low-resolution'), 0)
    self.assertEqual(self.rows('photos-without-people'), 1)                     # other checks: still there
    dismissed = self.client.get('/dashboard/loose-ends/low-resolution/?dismissed=1').content.decode()
    self.assertIn('Knipsel', dismissed)
    self.assertIn('Delpher, beter wordt het niet', dismissed)
    self.client.post('/dashboard/loose-ends/low-resolution/', {'object_id': self.clipping.pk, 'action': 'restore'})
    self.assertEqual(self.rows('low-resolution'), 1)

  def test_only_what_the_loose_end_holds(self):
    from content.models import Content
    sharp = Content.objects.create(name='Scherp', kind='photo', user=self.editor, status='p', visibility='c', width=4000, height=3000)
    self.assertEqual(self.client.post('/dashboard/loose-ends/low-resolution/', {'object_id': sharp.pk}).status_code, 404)
    self.assertEqual(self.client.post('/dashboard/loose-ends/marked/', {'object_id': self.clipping.pk}).status_code, 404)
    reader = Client()
    reader.force_login(self.reader)
    self.assertEqual(reader.post('/dashboard/loose-ends/low-resolution/', {'object_id': self.clipping.pk}).status_code, 404)

  def test_goes_with_its_item(self):
    from dashboard.models import LooseEndDismissal
    self.client.post('/dashboard/loose-ends/low-resolution/', {'object_id': self.clipping.pk})
    self.assertEqual(LooseEndDismissal.objects.count(), 1)
    self.clipping.delete()
    self.assertEqual(LooseEndDismissal.objects.count(), 0)



class NoPortraitTests(DashboardTestCase):
  """People without a portrait who are tagged in a photo the viewer may see."""

  def test_who(self):
    from content.models import Content, Portrait
    tagged, framed, absent = self.person('Getagd'), self.person('Ingelijst'), self.person('Afwezig')
    photo = Content.objects.create(name='Feest', kind='photo', user=self.editor, status='p', visibility='c', file='content/2026/feest.jpg')
    photo.people.set([tagged, framed])
    Portrait.objects.create(person=framed, content=photo, is_primary=True)
    letter = Content.objects.create(name='Brief', kind='document', user=self.editor, status='p', visibility='c', file='content/2026/brief.jpg')
    letter.people.set([absent])                                              # a document, not a photo
    self.assertEqual(list(blocks.loose_end_items('no-portrait', self.request(self.editor))), [tagged])

  def test_choose_portrait_goes_straight_to_the_dialog(self):
    from content.models import Content
    person = self.person('Getagd')
    Content.objects.create(name='Feest', kind='photo', user=self.editor, status='p', visibility='c', file='content/2026/feest.jpg').people.set([person])
    client = Client()
    client.force_login(self.editor)
    html = client.get('/dashboard/loose-ends/no-portrait/').content.decode().replace('"', '')
    self.assertIn(f'value={person.page_url()}?open=portrait', html)
    response = client.post('/ui/edit/', {'on': '1', 'next': f'{person.page_url()}?open=portrait'})
    self.assertEqual(response.url, f'{person.page_url()}?open=portrait')


class NoTranscriptTests(DashboardTestCase):
  """Scanned documents without a transcript - images, not PDFs (yet)."""

  def test_which(self):
    from content.models import Content, Transcript
    make = lambda name, file: Content.objects.create(name=name, kind='document', user=self.editor, status='p', visibility='c', file=file)
    scan, pdf, done = make('Brief', 'content/2026/brief.jpg'), make('Akte', 'content/2026/akte.pdf'), make('Kaart', 'content/2026/kaart.png')
    Transcript.objects.create(content=done, kind='original', language='nl', method='manual', text='Klaar')
    self.assertEqual(list(blocks.loose_end_items('no-transcript', self.request(self.editor))), [scan])


class BooksWithoutAuthorTests(DashboardTestCase):
  """Books without an author linked as a person - the author as written on
  the book first, the actionable ones."""

  def test_which_and_order(self):
    from content.models import Content
    make = lambda name, author: Content.objects.create(name=name, kind='book', user=self.editor, status='p', visibility='c') if author is None else self.book(name, author)
    unknown, written, linked = make('Atlas', ''), make('Zuid', 'Jeroen Brouwers'), make('Bezonken rood', 'Jeroen Brouwers')
    linked.book_detail.authors.add(self.person('Jeroen'))
    no_detail = make('Album', None)                                             # no BookContent row at all
    Content.objects.create(name='Hoofdstuk 1', kind='book', user=self.editor, status='p', visibility='c', parent=written)   # a part: under its book
    self.assertEqual(list(blocks.loose_end_items('books-without-author', self.request(self.editor))), [written, no_detail, unknown])

  def test_row_shows_the_written_author(self):
    self.book('Zuid', 'Jeroen Brouwers')
    client = Client()
    client.force_login(self.editor)
    html = client.get('/dashboard/loose-ends/books-without-author/').content.decode()
    self.assertIn('Jeroen Brouwers', html)

  def book(self, name, author):
    from content.models import Content
    item = Content.objects.create(name=name, kind='book', user=self.editor, status='p', visibility='c')
    item.ensure_detail()
    type(item.book_detail).objects.filter(pk=item.book_detail.pk).update(author=author)
    item.refresh_from_db()
    return item


class AccountsTests(DashboardTestCase):
  """dashboard/accounts/: waiting accounts approved or declined, activity -
  for staff who may change users."""

  def setUp(self):
    super().setUp()
    User = get_user_model()
    self.staff = self.user('beheer', 'change_user')
    self.staff.is_staff = True
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)
    self.new = User.objects.create(username='nieuw', is_active=False)

  def test_only_staff_who_may_change_users(self):
    other = Client()
    other.force_login(self.editor)
    self.assertEqual(other.get('/dashboard/accounts/').status_code, 404)
    page = self.client.get('/dashboard/accounts/').content.decode()
    self.assertIn('nieuw', page)
    self.assertIn('/dashboard/accounts/', self.client.get('/').content.decode())     # the dashboard block

  def test_approve_and_decline(self):
    from django.contrib.auth.models import Group
    Group.objects.create(name='Visitors')
    with self.settings(REGISTER_DEFAULT_GROUPS=['Visitors']):
      self.client.post('/dashboard/accounts/', {'account': self.new.pk, 'action': 'approve'})
    self.new.refresh_from_db()
    self.assertTrue(self.new.is_active)
    self.assertTrue(self.new.groups.filter(name='Visitors').exists())
    other = get_user_model().objects.create(username='nee', is_active=False)
    self.client.post('/dashboard/accounts/', {'account': other.pk, 'action': 'decline'})
    self.assertFalse(get_user_model().objects.filter(pk=other.pk).exists())
    # Someone who signed in before is never deleted from here.
    self.reader.is_active = False
    self.reader.save()
    get_user_model().objects.filter(pk=self.reader.pk).update(last_login='2026-01-01T00:00:00Z')
    self.client.post('/dashboard/accounts/', {'account': self.reader.pk, 'action': 'decline'})
    self.assertTrue(get_user_model().objects.filter(pk=self.reader.pk).exists())

  def test_activity(self):
    from dashboard import accounts
    from notes.models import Note
    Note.objects.create(user=self.editor, title='Vraag')
    rows = {a.username: a for a in accounts.activity()}
    self.assertEqual(rows['editor'].last_activity_kind, 'note')
    self.assertIsNone(rows['reader'].last_activity)


class NumbersTests(DashboardTestCase):
  """The archive in numbers: comments, notes and tags too - each as far as
  this viewer may see it."""

  def test_counts(self):
    from notes.models import Note
    Note.objects.create(user=self.editor, title='Gedeeld', status='p', visibility='c')
    Note.objects.create(user=self.editor, title='Alleen van mij', status='p', visibility='q')
    self.assertEqual(blocks.numbers(self.request(self.editor))['notes'], 2)
    self.assertEqual(blocks.numbers(self.request(self.reader))['notes'], 1)   # someone else's private note: not counted
    client = Client()
    client.force_login(self.reader)
    html = client.get('/').content.decode().replace('"', '')
    self.assertIn('href=/notes/', html)
    self.assertIn('href=/comments/', html)
