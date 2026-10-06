import json

from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content
from core.models import Tag


class TagEditingTests(TestCase):
  """Tags on an item's page in edit mode (cmnsd EditableRelationsMixin:
  link / unlink, Content.api_editable_relations; content/_tag_chip.html)."""

  def setUp(self):
    self.editor = self.user('editor', 'change_content')
    self.creator = self.user('creator', 'change_content', 'add_tag')
    self.member = self.user('member')
    self.item = Content.objects.create(name='Foto', kind='photo', user=self.editor, status='p', visibility='c')
    self.boot = Tag.objects.create(name='boot', user=self.editor, status='p', visibility='c')
    self.linked = Tag.objects.create(name='medan', user=self.editor, status='p', visibility='c')
    self.item.tags.add(self.linked)

  def user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def client_for(self, user, edit=True):
    client = Client()
    client.force_login(user)
    if edit:
      client.post('/ui/edit/', {'on': '1', 'next': '/'})
    return client

  def act(self, action, data, user=None):
    client = self.client_for(user or self.editor)
    return client.post(f'/api/content/{self.item.token}/{action}/', json.dumps(data), content_type='application/json')

  def tags(self):
    return set(self.item.tags.values_list('name', flat=True))

  def test_link_returns_the_chip_with_count_and_remove(self):
    response = self.act('link', {'relation': 'tags', 'token': self.boot.token})
    self.assertEqual(response.status_code, 200)
    self.assertEqual(self.tags(), {'boot', 'medan'})
    html = response.json()['html'].replace('"', '')
    self.assertIn('boot <span class=tag__count>1</span>', html)
    self.assertIn('data-cmnsd-action=unlink', html)
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.item.pk), change_message='Added tags: boot').exists())

  def test_unlink_keeps_the_tag(self):
    self.assertEqual(self.act('unlink', {'relation': 'tags', 'token': self.linked.token}).status_code, 200)
    self.assertEqual(self.tags(), set())
    self.assertTrue(Tag.objects.filter(pk=self.linked.pk).exists())

  def test_refusals(self):
    other = get_user_model().objects.create(username='other')
    draft = Tag.objects.create(name='werktitel', user=other, status='c', visibility='c')   # not visible to the editor
    cases = [
      ({'relation': 'people', 'token': self.boot.token}, 400),     # not an editable relation (yet)
      ({'relation': 'tags', 'token': draft.token}, 400),           # can't see it
      ({'relation': 'tags', 'token': self.linked.token}, 400),     # already linked
      ({'relation': 'tags', 'name': 'nieuw'}, 400),                # no add_tag permission
    ]
    for data, status in cases:
      with self.subTest(data=data):
        self.assertEqual(self.act('link', data).status_code, status)
    self.assertEqual(self.act('link', {'relation': 'tags', 'token': self.boot.token}, user=self.member).status_code, 403)
    self.assertEqual(self.tags(), {'medan'})

  def test_create_a_tag_published_for_members(self):
    response = self.act('link', {'relation': 'tags', 'name': 'Bandung 1950'}, user=self.creator)
    self.assertEqual(response.status_code, 200)
    tag = Tag.objects.get(name='Bandung 1950')
    self.assertEqual((tag.status, tag.visibility, tag.user), ('p', 'c', self.creator))
    self.assertIn('Bandung 1950', self.tags())
    self.assertTrue(LogEntry.objects.filter(object_id=str(tag.pk), action_flag=ADDITION).exists())

  def test_create_with_an_existing_name_links_that_tag(self):
    self.act('link', {'relation': 'tags', 'name': 'BOOT'}, user=self.creator)
    self.assertEqual(Tag.objects.filter(name__iexact='boot').count(), 1)
    self.assertIn('boot', self.tags())

  def test_page_offers_create_only_with_add_permission(self):
    page = lambda user: self.client_for(user).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-picker-create', page(self.creator))
    editor_page = page(self.editor)
    self.assertIn('data-cmnsd-picker=tag', editor_page)
    self.assertNotIn('data-picker-create', editor_page)
    self.assertNotIn('chip-edit', self.client_for(self.editor, edit=False).get(self.item.get_absolute_url()).content.decode())

  def test_tag_picker_format(self):
    html = self.client_for(self.editor).get('/api/tag/?q=boo&format=picker').json()['html'].replace('"', '')
    self.assertIn(f'data-picker-choose={self.boot.token}', html)
    self.assertIn('data-picker-name=boot', html)

  def test_actions_confirm_in_messages(self):
    # (the edit-mode switch's own "Edit mode is on." comes along with the
    # first response - nothing loaded the page in between)
    added = self.act('link', {'relation': 'tags', 'token': self.boot.token}).json()['messages']
    self.assertIn({'text': 'Tag “boot” added.', 'level': 'success', 'tags': 'success'}, added)
    created = self.act('link', {'relation': 'tags', 'name': 'Nieuw'}, user=self.creator).json()['messages']
    self.assertIn('Tag “Nieuw” created and added.', [m['text'] for m in created])
    removed = self.act('unlink', {'relation': 'tags', 'token': self.boot.token}).json()['messages']
    self.assertIn('Tag “boot” removed.', [m['text'] for m in removed])


class PeopleEditingTests(TestCase):
  """People on an item's page in edit mode - the same link / unlink as
  tags, no direct create: the picker links to the add page."""
  setUp = TagEditingTests.setUp
  user = TagEditingTests.user
  client_for = TagEditingTests.client_for
  act = TagEditingTests.act

  def person(self, given, last=''):
    from people.models import Person
    return Person.objects.create(given_name=given, last_name=last, user=self.editor, status='p', visibility='c')

  def test_link_returns_the_row_and_unlink_removes(self):
    eric = self.person('Eric', 'Coomans')
    response = self.act('link', {'relation': 'people', 'token': eric.token})
    self.assertEqual(response.status_code, 200)
    html = response.json()['html'].replace('"', '')
    self.assertIn('person-row', html)
    self.assertIn('data-cmnsd-action=unlink', html)
    self.assertIn('Person “Eric Coomans” added.', [m['text'] for m in response.json()['messages']])
    self.act('unlink', {'relation': 'people', 'token': eric.token})
    self.assertFalse(self.item.people.exists())

  def test_no_direct_create(self):
    self.assertEqual(self.act('link', {'relation': 'people', 'name': 'Nieuw Mens'}, user=self.creator).status_code, 400)

  def test_new_person_link_only_with_add_permission(self):
    adder = self.user('adder', 'change_content', 'add_person')
    page = lambda user: self.client_for(user).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-picker-new-dialog=/api/person/new/', page(adder))
    self.assertIn('data-cmnsd-picker=person', page(self.editor))
    self.assertNotIn('data-picker-new-url', page(self.editor))

  def test_picker_ranks_name_starts_first(self):
    self.person('Frederica')        # contains "eric", not at a word start
    self.person('Jan', 'Eric')      # a word starts with "eric"
    self.person('Eric', 'Bake')     # the name starts with "eric"
    html = self.client_for(self.editor).get('/api/person/?q=eric&format=picker').json()['html']
    order = [name for name in ('Eric Bake', 'Jan Eric', 'Frederica') if name in html]
    self.assertEqual(sorted(order, key=html.index), ['Eric Bake', 'Jan Eric', 'Frederica'])
    self.assertIn('Fred<mark class=search-hit>eric</mark>a', html)   # the search term marked (minified: no quotes)


class PlaceEditingTests(TestCase):
  """Places on an item's page in edit mode - created from the picker
  (one field, no status), context added later or as "Parent: Child"."""
  setUp = TagEditingTests.setUp
  user = TagEditingTests.user
  client_for = TagEditingTests.client_for
  act = TagEditingTests.act

  def place(self, name, parent=None):
    from places.models import Place
    return Place.objects.create(name=name, parent=parent, user=self.editor)

  def test_link_and_unlink(self):
    bandung = self.place('Bandung')
    response = self.act('link', {'relation': 'places', 'token': bandung.token})
    self.assertEqual(response.status_code, 200)
    self.assertIn('tag--place', response.json()['html'])
    self.assertEqual(list(self.item.places.all()), [bandung])
    self.act('unlink', {'relation': 'places', 'token': bandung.token})
    self.assertFalse(self.item.places.exists())

  def test_create_needs_add_place(self):
    from places.models import Place
    self.assertEqual(self.act('link', {'relation': 'places', 'name': 'New York'}).status_code, 400)
    adder = self.user('adder', 'change_content', 'add_place')
    response = self.act('link', {'relation': 'places', 'name': 'New York'}, user=adder)
    self.assertEqual(response.status_code, 200)
    self.assertIn('Place “New York” created and added.', [m['text'] for m in response.json()['messages']])
    self.assertEqual(Place.objects.get(name='New York').user, adder)

  def test_create_with_parent(self):
    from places.models import Place
    usa = self.place('U.S.A.')
    adder = self.user('adder', 'change_content', 'add_place')
    self.act('link', {'relation': 'places', 'name': 'U.S.A.: New York'}, user=adder)
    new_york = self.item.places.get()
    self.assertEqual((new_york.name, new_york.parent), ('New York', usa))
    self.assertEqual(Place.objects.filter(name='U.S.A.').count(), 1)   # the existing parent reused

  def test_picker_shows_parents_and_is_public(self):
    usa = self.place('U.S.A.')
    state = self.place('New York (state)', parent=usa)
    self.place('New York', parent=state)
    html = Client().get('/api/place/?q=new+york&format=picker').json()['html']
    self.assertIn('New York (state) · U.S.A.', html)


class EventEditingTests(TestCase):
  """Events on an item's page in edit mode - linked, never created here
  (the picker links to the add page); shown as the viewer may see them."""
  setUp = TagEditingTests.setUp
  user = TagEditingTests.user
  client_for = TagEditingTests.client_for
  act = TagEditingTests.act

  def event(self, *people, **fields):
    from events.models import Event
    event = Event.objects.create(user=self.editor, **{'kind': Event.Kind.BIRTH, **fields})
    event.people.add(*people)
    return event

  def test_link_unlink_and_obfuscated_row(self):
    from people.models import Person
    eric = Person.objects.create(given_name='Eric', user=self.editor, status='p', visibility='c')
    other = get_user_model().objects.create(username='other')
    secret = Person.objects.create(given_name='Geheim', user=other, status='p', visibility='q')
    marriage = self.event(eric, secret, kind='marriage', year=1968)
    response = self.act('link', {'relation': 'events', 'token': marriage.token})
    self.assertEqual(response.status_code, 200)
    html = response.json()['html']
    self.assertIn('Eric', html)
    self.assertNotIn('Geheim', html)                          # row and the "×" tooltip
    self.assertNotIn('Geheim', str(response.json()['messages']))   # nor the confirmation
    self.act('unlink', {'relation': 'events', 'token': marriage.token})
    self.assertFalse(self.item.events.exists())

  def test_no_direct_create_and_new_event_link(self):
    self.assertEqual(self.act('link', {'relation': 'events', 'name': 'Iets'}, user=self.creator).status_code, 400)
    adder = self.user('adder', 'change_content', 'add_event')
    html = self.client_for(adder).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-picker=event', html)
    self.assertIn('data-picker-new-dialog=/api/event/new/', html)


class AuthorEditingTests(TestCase):
  """A book's linked authors (BookContent.authors) in edit mode - the
  people picker, only for a book."""
  setUp = TagEditingTests.setUp
  user = TagEditingTests.user
  client_for = TagEditingTests.client_for
  act = TagEditingTests.act

  def test_link_and_unlink_on_a_book(self):
    from people.models import Person
    self.item.kind = 'book'
    self.item.save()
    author = Person.objects.create(given_name='Hella', last_name='Haasse', user=self.editor, status='p', visibility='c')
    response = self.act('link', {'relation': 'authors', 'token': author.token})
    self.assertEqual(response.status_code, 200)
    self.assertEqual(list(self.item.book_detail.authors.all()), [author])
    html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('id=content-authors', html)
    self.act('unlink', {'relation': 'authors', 'token': author.token})
    self.assertFalse(self.item.book_detail.authors.exists())

  def test_not_on_a_photo_even_with_a_leftover_book_detail(self):
    from people.models import Person
    self.item.kind = 'book'
    self.item.save()                      # creates the book detail
    self.item.kind = 'photo'
    self.item.save()                      # the detail row stays
    author = Person.objects.create(given_name='Hella', user=self.editor, status='p', visibility='c')
    self.assertEqual(self.act('link', {'relation': 'authors', 'token': author.token}).status_code, 400)
