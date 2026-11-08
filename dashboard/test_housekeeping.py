import io
import shutil
import tempfile
from pathlib import Path

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class HousekeepingTests(TestCase):
  """dashboard/housekeeping/ (dashboard/housekeeping.py): staff who may
  delete content; purging deleted items and removing files without a
  record, each only after a confirmation page."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    User = get_user_model()
    self.staff = User.objects.create(username='beheer', is_staff=True)
    self.staff.user_permissions.add(Permission.objects.get(codename='delete_content'))
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)

  def item(self, name, status='p', parent=None):
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'white').save(buffer, 'JPEG')
    item = Content.objects.create(name=name, kind='photo', user=self.staff, status=status, visibility='c', parent=parent)
    item.file.save(f'{name}.jpg', ContentFile(buffer.getvalue()))
    return item

  def test_staff_who_may_delete_only(self):
    editor = get_user_model().objects.create(username='redacteur')
    editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    editor.save()
    client = Client()
    client.force_login(editor)
    self.assertEqual(client.get('/dashboard/housekeeping/').status_code, 404)
    self.assertNotIn('/dashboard/housekeeping/', client.get('/people/').content.decode())   # nor in their menu
    self.assertEqual(self.client.get('/dashboard/housekeeping/').status_code, 200)
    self.assertIn('/dashboard/housekeeping/', self.client.get('/people/').content.decode())  # in the user menu

  def test_purge_after_confirmation(self):
    gone = self.item('weg', status='x')
    path = Path(gone.file.path)
    kept = self.item('blijft')
    first = self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [gone.token, kept.token]})
    self.assertContains(first, 'weg')
    self.assertTrue(Content.objects.filter(pk=gone.pk).exists())          # not yet: only the list
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [gone.token, kept.token], 'confirm': '1'})
    self.assertFalse(Content.objects.filter(pk=gone.pk).exists())
    self.assertFalse(path.exists())
    self.assertTrue(Content.objects.filter(pk=kept.pk).exists())           # not deleted: never purged
    self.assertTrue(LogEntry.objects.filter(object_id=str(gone.pk), action_flag=3).exists())

  def test_an_item_with_live_parts_stays(self):
    whole = self.item('boek', status='x')
    self.item('pagina', parent=whole)
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [whole.token], 'confirm': '1'})
    self.assertTrue(Content.objects.filter(pk=whole.pk).exists())

  def test_files_without_a_record(self):
    item = self.item('bekend')
    orphan = Path(MEDIA) / 'content' / '2020' / 'los.jpg'
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b'x')
    page = self.client.get('/dashboard/housekeeping/orphans/').content.decode()
    self.assertIn('content/2020/los.jpg', page)
    self.assertNotIn(f'value="{item.file.name}"', page)
    self.client.post('/dashboard/housekeeping/', {'action': 'files', 'file': ['content/2020/los.jpg', item.file.name, '../db.sqlite3'], 'confirm': '1'})
    self.assertFalse(orphan.exists())
    self.assertTrue(Path(item.file.path).exists())                         # has a record: never deleted

  def test_a_deleted_duplicate_is_purged_from_its_pair(self):
    kept = self.item('origineel')
    copy = self.item('kopie', status='x')
    Content.objects.filter(pk__in=[kept.pk, copy.pk]).update(checksum='a' * 64)
    page = self.client.get('/dashboard/housekeeping/duplicates/').content.decode().replace('"', '')
    self.assertIn('<h1 class=tag-page__name>Same file twice', page)              # a page of its own
    self.assertIn(f'value={copy.token}', page)
    self.assertNotIn(f'value={kept.token}', page)                         # not deleted: no checkbox
    path = Path(copy.file.path)
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [copy.token], 'confirm': '1'})
    self.assertFalse(Content.objects.filter(pk=copy.pk).exists())
    self.assertFalse(path.exists())
    self.assertTrue(Path(kept.file.path).exists())

  def test_a_file_shared_with_another_item_is_kept(self):
    kept = self.item('origineel')
    copy = Content.objects.create(name='zelfde', kind='photo', user=self.staff, status='x', visibility='c')
    Content.objects.filter(pk=copy.pk).update(file=kept.file.name)           # the very same stored file
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [copy.token], 'confirm': '1'})
    self.assertFalse(Content.objects.filter(pk=copy.pk).exists())
    self.assertTrue(Path(kept.file.path).exists())

  def test_overview_counts_and_section_pages(self):
    self.item('weg', status='x')
    page = self.client.get('/dashboard/housekeeping/').content.decode().replace('"', '')
    for section in ('revoked', 'deleted', 'duplicates', 'orphans', 'missing', 'unused-tags', 'unused-places'):
      self.assertIn(f'href=/dashboard/housekeeping/{section}/', page)
      self.assertEqual(self.client.get(f'/dashboard/housekeeping/{section}/').status_code, 200)
    self.assertRegex(page, r'<span class=tag__count>1</span> deleted, to purge')
    self.assertIn('class=is-clear', page)                                       # an empty section stays, muted
    self.assertEqual(self.client.get('/dashboard/housekeeping/nonsense/').status_code, 404)

  def test_after_a_delete_back_to_the_section(self):
    gone = self.item('weg', status='x')
    response = self.client.post('/dashboard/housekeeping/deleted/', {'action': 'purge', 'item': [gone.token], 'confirm': '1'})
    self.assertRedirects(response, '/dashboard/housekeeping/deleted/', fetch_redirect_response=False)

  def test_revoked_items_with_their_reason(self):
    from core.models import Comment
    revoked = self.item('ingetrokken', status='r')
    Comment.objects.create(target=revoked, user=self.staff, name='Revocation reason', content='Dubbel met de scan', status='p', visibility='c')
    Comment.objects.create(target=revoked, user=self.staff, content='Nee, de achterkant is anders', status='p', visibility='c')
    self.item('gewoon')
    page = self.client.get('/dashboard/housekeeping/revoked/').content.decode().replace('"', '')
    self.assertIn('ingetrokken', page)
    self.assertNotIn('gewoon', page)
    self.assertLess(page.index('Dubbel met de scan'), page.index('Nee, de achterkant is anders'))   # the discussion, in order
    self.assertIn('<strong>Revocation reason</strong>', page)
    self.assertNotIn('<input type=checkbox', page)                             # decided on its page, not here

  def test_revoked_people_events_and_notes_too(self):
    """One review queue, by kind: a revoked person with the reason given,
    an event, a note (no comments - no discussion)."""
    from core.models import Comment
    from events.models import Event
    from notes.models import Note
    from people.models import Person
    person = Person.objects.create(given_name='Dubbelganger', user=self.staff, status='r', visibility='c')
    Comment.objects.create(target=person, user=self.staff, name='Revocation reason', content='Zelfde als Jan', status='p', visibility='c')
    Person.objects.create(given_name='Gewoonmens', user=self.staff, status='p', visibility='c')
    Event.objects.create(title='Verkeerd feest', kind='other', user=self.staff, status='r')
    Note.objects.create(title='Oude vraag', user=self.staff, status='r', visibility='c')
    page = self.client.get('/dashboard/housekeeping/revoked/').content.decode().replace('"', '')
    for shown in ('Dubbelganger', 'Zelfde als Jan', 'Verkeerd feest', 'Oude vraag', 'People', 'Events', 'Notes'):
      self.assertIn(shown, page)
    self.assertNotIn('Gewoonmens', page)
    self.assertLess(page.index('People'), page.index('Events'))

  def test_staff_open_a_deleted_item_marked_deleted(self):
    gone = self.item('verwijderd', status='x')
    page = self.client.get(gone.get_absolute_url())
    self.assertContains(page, 'content-detail__deleted')
    self.assertEqual(self.client.get(f'/content/{gone.token}/thumb/card/').status_code, 200)
    self.assertNotContains(self.client.get('/content/'), 'verwijderd')     # never in a list
    member = get_user_model().objects.create(username='lid')
    member.save()
    client = Client()
    client.force_login(member)
    self.assertEqual(client.get(gone.get_absolute_url()).status_code, 404)
    self.assertEqual(client.get(f'/content/{gone.token}/thumb/card/').status_code, 404)

  def test_comments_on_a_deleted_item_show_on_its_page_only(self):
    from core.models import Comment
    gone = self.item('verwijderd', status='x')
    Comment.objects.create(target=gone, user=self.staff, content='Een dubbele', status='p')
    self.assertContains(self.client.get(gone.get_absolute_url()), 'Een dubbele')
    self.assertNotContains(self.client.get('/comments/'), 'Een dubbele')    # not in the feed

  def test_a_deleted_items_sections_are_never_folded(self):
    whole = self.item('verwijderd boek', status='x')
    self.item('pagina', parent=whole)
    html = self.client.get(whole.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('data-cmnsd-section=content.parts', html)               # plain, not a fold
    self.assertIn('pagina', html)


class UnusedTagsAndPlacesTests(TestCase):
  """Housekeeping: unused tags and places (issue #460) - listed by eye,
  deleted after a confirmation, by staff who may delete them."""

  def setUp(self):
    from core.models import Tag
    from places.models import Place
    User = get_user_model()
    self.staff = User.objects.create(username='beheer', is_staff=True)
    for codename in ('delete_content', 'delete_tag', 'delete_place'):
      self.staff.user_permissions.add(Permission.objects.get(codename=codename))
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)
    make_tag = lambda name, **f: Tag.objects.create(name=name, user=self.staff, status='p', visibility='c', **f)
    self.old_category, self.used = make_tag('Advertisement'), make_tag('Krangan 81')
    self.collection = make_tag('Collection')
    make_tag('Boeken', parent=self.collection)                                   # Collection has a child: used
    from core.tags import LOOSE_END_SLUG
    make_tag('Loose end', slug=LOOSE_END_SLUG)                                    # never offered
    Content.objects.create(name='Foto', kind='photo', user=self.staff, status='p', visibility='c').tags.add(self.used)
    make_place = lambda name, **f: Place.objects.create(name=name, user=self.staff, **f)
    self.lone, self.batavia, self.djakarta = make_place('Nieuw Guinea'), make_place('Batavia'), make_place('Djakarta')
    self.batavia.alternatives.add(self.djakarta)                                  # another era's name: used

  def test_listed(self):
    from dashboard import housekeeping
    self.assertEqual([t.name for t in housekeeping.unused_tags()], ['Advertisement', 'Boeken'])
    self.assertEqual([p.name for p in housekeeping.unused_places()], ['Nieuw Guinea'])
    self.assertIn('Advertisement', self.client.get('/dashboard/housekeeping/unused-tags/').content.decode())
    self.assertIn('Nieuw Guinea', self.client.get('/dashboard/housekeeping/unused-places/').content.decode())

  def test_delete_after_confirmation_and_recheck(self):
    from core.models import Tag
    confirm = self.client.post('/dashboard/housekeeping/', {'action': 'tags', 'object': [self.old_category.token]})
    self.assertContains(confirm, 'Advertisement')                                  # the confirmation page
    self.assertTrue(Tag.objects.filter(pk=self.old_category.pk).exists())
    Content.objects.create(name='Advertentie', kind='document', user=self.staff, status='p', visibility='c').tags.add(self.old_category)
    self.client.post('/dashboard/housekeeping/', {'action': 'tags', 'object': [self.old_category.token], 'confirm': '1'})
    self.assertTrue(Tag.objects.filter(pk=self.old_category.pk).exists())         # used in between: kept
    self.client.post('/dashboard/housekeeping/', {'action': 'places', 'object': [self.lone.token], 'confirm': '1'})
    from places.models import Place
    self.assertFalse(Place.objects.filter(pk=self.lone.pk).exists())
    self.assertTrue(LogEntry.objects.filter(change_message__contains='housekeeping (unused)').exists())

  def test_needs_the_delete_permission(self):
    self.staff.user_permissions.remove(Permission.objects.get(codename='delete_place'))
    staff = get_user_model().objects.get(pk=self.staff.pk)
    client = Client()
    client.force_login(staff)
    self.assertEqual(client.post('/dashboard/housekeeping/', {'action': 'places', 'object': [self.lone.token], 'confirm': '1'}).status_code, 404)
    html = client.get('/dashboard/housekeeping/unused-places/').content.decode().replace('"', '')
    self.assertNotIn(f'value={self.lone.token}', html)                            # listed, without a checkbox
    self.assertIn('Nieuw Guinea', html)


class LinkedTwiceTests(TestCase):
  """Housekeeping: people linked to an item that also documents an event
  they took part in (dashboard/housekeeping.py linked_twice) - only where
  the direct link adds nothing: no role or subject, no frame, not a photo,
  not through a historical event."""

  def setUp(self):
    from events.models import Event
    from people.models import Person
    User = get_user_model()
    self.staff = User.objects.create(username='beheer2', is_staff=True)
    for codename in ('delete_content', 'change_content'):
      self.staff.user_permissions.add(Permission.objects.get(codename=codename))
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)
    person = lambda name: Person.objects.create(given_name=name, user=self.staff, status='p', visibility='c')
    self.bride, self.groom, self.parent = person('Bruid'), person('Bruidegom'), person('Ouder')
    self.marriage = Event.objects.create(kind='marriage', year=1889, user=self.staff, status='p')
    self.marriage.people.add(self.bride, self.groom)

  def item(self, name, kind='document', events=()):
    item = Content.objects.create(name=name, kind=kind, user=self.staff, status='p', visibility='c')
    item.events.add(*events)
    return item

  def found(self):
    from dashboard.housekeeping import linked_twice
    return {(group['content'].name, link['person'].given_name) for group in linked_twice() for row in group['events'] for link in row['direct']}

  def test_only_where_the_link_adds_nothing(self):
    from content.models import ContentPerson
    from events.models import Event
    ad = self.item('Advertentie', events=[self.marriage])
    ad.people.add(self.bride, self.parent)                                       # the parent wasn't on the event
    ad.people.add(self.groom, through_defaults={'role': 'subject'})
    letter = self.item('Brief', events=[self.marriage])
    letter.people.add(self.bride, through_defaults={'role': 'creator'})          # a role that says more
    photo = self.item('Trouwfoto', kind='photo', events=[self.marriage])
    photo.people.add(self.bride)                                                 # who's on a photo
    framed = self.item('Akte', events=[self.marriage])
    framed.people.add(self.groom)
    ContentPerson.objects.filter(content=framed).update(region_x=.1, region_y=.1, region_w=.2, region_h=.2)
    history = Event.objects.create(kind='historical', year=1889, user=self.staff, status='p')
    history.people.add(self.parent)
    clipping = self.item('Krant', events=[history])
    clipping.people.add(self.parent)                                             # history isn't anyone's own
    self.assertEqual(self.found(), {('Advertentie', 'Bruid'), ('Advertentie', 'Bruidegom')})

  def test_the_page_and_removing_a_link(self):
    ad = self.item('Advertentie', events=[self.marriage])
    ad.people.add(self.bride)
    page = self.client.get('/dashboard/housekeeping/linked-twice/').content.decode()
    self.assertIn('Advertentie', page)
    self.assertIn('data-cmnsd-action', page)
    self.assertIn('Bruidegom', page)                                             # who took part, also when not linked directly
    ad.people.remove(self.bride)
    self.assertEqual(self.found(), set())


class PurgeRecordsTests(TestCase):
  """Deleted people, events, notes and comments, to purge (housekeeping.
  deleted_items): listed by kind with what goes along; purged after the
  confirmation - a person with the events only they are in, never one with
  a user account; links and comments go with them, the rest stays."""

  def setUp(self):
    from people.models import Person
    User = get_user_model()
    self.staff = User.objects.create(username='beheer', is_staff=True)
    self.staff.user_permissions.add(Permission.objects.get(codename='delete_content'))
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)
    self.person = Person.objects.create(given_name='Willem', last_name='Warnaar', user=self.staff, status='x', visibility='c')
    self.other = Person.objects.create(given_name='Anna', user=self.staff, status='p', visibility='c')

  def purge(self, *values, confirm=True):
    return self.client.post('/dashboard/housekeeping/deleted/', {'action': 'purge', 'item': list(values), **({'confirm': '1'} if confirm else {})})

  def test_listed_by_kind(self):
    from notes.models import Note
    Note.objects.create(title='Klad', user=self.staff, status='x')
    page = self.client.get('/dashboard/housekeeping/deleted/').content.decode().replace('"', '')
    self.assertIn(f'value=person:{self.person.token}', page)
    self.assertIn('Klad', page)
    self.assertIn('People', page)

  def test_a_person_with_their_own_events(self):
    from events.models import Event
    from people.models import Person, PersonRelation
    birth = Event.objects.create(kind='birth', year=1880, user=self.staff, status='p')
    birth.people.add(self.person)
    marriage = Event.objects.create(kind='marriage', year=1905, user=self.staff, status='p')
    marriage.people.add(self.person, self.other)
    PersonRelation.objects.create(person_from=self.person, person_to=self.other, relation_type='partner')
    item = Content.objects.create(name='Foto', kind='photo', user=self.staff, status='p', visibility='c')
    item.people.add(self.person)
    confirm = self.purge(f'person:{self.person.token}', confirm=False).content.decode()
    self.assertIn('1 own event', confirm)
    self.assertIn('in 1 event with others', confirm)
    self.purge(f'person:{self.person.token}')
    self.assertFalse(Person.objects.filter(pk=self.person.pk).exists())
    self.assertFalse(Event.objects.filter(pk=birth.pk).exists())                 # theirs alone: gone
    self.assertEqual(list(Event.objects.get(pk=marriage.pk).people.all()), [self.other])   # with others: stays
    self.assertFalse(PersonRelation.objects.exists())
    self.assertTrue(Content.objects.filter(pk=item.pk).exists())
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.person.pk), change_message='Purged in housekeeping').exists())

  def test_never_a_person_with_a_user_account(self):
    from people.models import Person
    self.person.related_user = get_user_model().objects.create(username='willem')
    self.person.save()
    self.assertIn('has a user account', self.client.get('/dashboard/housekeeping/deleted/').content.decode())
    self.purge(f'person:{self.person.token}')
    self.assertTrue(Person.objects.filter(pk=self.person.pk).exists())

  def test_only_what_is_deleted(self):
    from people.models import Person
    self.purge(f'person:{self.other.token}', 'nonsense:abc', 'person:')
    self.assertTrue(Person.objects.filter(pk=self.other.pk).exists())

  def test_an_event_note_and_comment(self):
    from core.models import Comment
    from events.models import Event
    from notes.models import Note
    event = Event.objects.create(kind='historical', title='Oorlog', year=1942, user=self.staff, status='x')
    event.people.add(self.other)
    note = Note.objects.create(title='Klad', body=f'Over [Anna](person:{self.other.token})', user=self.staff, status='x')
    note.people.add(self.other)
    on_event = Comment.objects.create(target=self.other, content='Klopt dit?', user=self.staff, status='x')
    self.purge(f'event:{event.token}', f'note:{note.token}', f'comment:{on_event.token}')
    self.assertFalse(Event.objects.filter(pk=event.pk).exists())
    self.assertFalse(Note.objects.filter(pk=note.pk).exists())
    self.assertFalse(Comment.objects.filter(pk=on_event.pk).exists())
    self.assertTrue(self.other.__class__.objects.filter(pk=self.other.pk).exists())

  def test_what_its_linked_to_and_the_admin(self):
    """No link to its own page - that's gone - but to the admin and to what
    it's linked to, still there: an event's people and places, a person's
    family and anyone of the same name."""
    from events.models import Event
    from people.models import Person, PersonRelation
    from places.models import Place
    double = Person.objects.create(given_name='Willem', last_name='Warnaar', user=self.staff, status='p', visibility='c')
    PersonRelation.objects.create(person_from=self.other, person_to=self.person, relation_type='parent')
    place = Place.objects.create(name='Alphen', user=self.staff)
    birth = Event.objects.create(kind='birth', year=1986, user=self.staff, status='x')
    birth.people.add(self.other)
    birth.places.add(place)
    self.staff.is_superuser = True
    self.staff.save()
    page = self.client.get('/dashboard/housekeeping/deleted/').content.decode().replace('"', '')
    self.assertNotIn(f'href={self.person.get_absolute_url()}', page)
    self.assertIn(f'href=/admin/people/person/{self.person.pk}/change/', page)
    self.assertIn(f'href={double.get_absolute_url()}', page)                    # same name: a double?
    self.assertIn(f'href={self.other.get_absolute_url()}', page)                # family, and the birth's person
    self.assertIn(f'href={place.get_absolute_url()}', page)

  def test_mentions_counted(self):
    from notes.models import Note
    Note.objects.create(title='Onderzoek', body=f'Zie [Willem](person:{self.person.token})', user=self.staff, status='p')
    self.assertIn('mentioned in 1 text', self.client.get('/dashboard/housekeeping/deleted/').content.decode())
