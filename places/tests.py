from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content
from events.models import Event
from people.models import Person

from .models import Place


class PlaceTestCase(TestCase):
  """Nederlandsch-Indië › Java › Batavia, with Djakarta (another era) and
  an empty Bandoeng; a public and a private item and a public and a
  hidden event in Batavia."""

  def setUp(self):
    self.owner = self.user('owner')
    self.indie = Place.objects.create(name='Nederlandsch-Indië', user=self.owner)
    self.java = Place.objects.create(name='Java', parent=self.indie, user=self.owner)
    self.batavia = Place.objects.create(name='Batavia', parent=self.java, user=self.owner)
    self.bandoeng = Place.objects.create(name='Bandoeng', parent=self.java, user=self.owner)
    self.djakarta = Place.objects.create(name='Djakarta', user=self.owner)
    self.public = Content.objects.create(name='Haven', kind='photo', user=self.owner, status='p', visibility='p')
    self.private = Content.objects.create(name='Geheim', kind='photo', user=self.owner, status='p', visibility='q')
    self.public.places.add(self.batavia)
    self.private.places.add(self.batavia)
    shown = Person.objects.create(given_name='Pieter', user=self.owner, status='p', visibility='p')
    hidden = Person.objects.create(given_name='Verborgen', user=self.owner, status='p', visibility='q')
    Event.objects.create(kind=Event.Kind.BIRTH, year=1920, user=self.owner).people.add(shown)
    Event.objects.get(people=shown).places.add(self.batavia)
    hidden_event = Event.objects.create(kind=Event.Kind.BIRTH, year=1921, user=self.owner)
    hidden_event.people.add(hidden)
    hidden_event.places.add(self.batavia)

  def user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def client_for(self, user, edit=False):
    client = Client()
    client.force_login(user)
    if edit:
      client.post('/ui/edit/', {'on': '1', 'next': '/'})
    return client

  def html(self, url, client=None):
    return (client or self.client).get(url).content.decode().replace('"', '')


class PlaceOverviewTests(PlaceTestCase):
  """/places/ (PlaceListView): a tree with counts; empty places only in edit mode."""

  def test_tree_with_counts_for_this_viewer(self):
    html = self.html('/places/')
    self.assertIn('Nederlandsch-Indië', html)                              # a heading: it holds Java
    self.assertIn('Batavia', html)
    self.assertRegex(html, r'Batavia</a> <span title=1 item · 1 event class=tag__count>2</span>')   # public item + visible event
    self.assertNotIn('Bandoeng', html)                                     # nothing there
    self.assertNotIn('Djakarta', html)

  def test_edit_mode_lists_every_place(self):
    editor = self.user('editor', 'change_place')
    html = self.html('/places/', self.client_for(editor, edit=True))
    self.assertIn('Bandoeng', html)
    self.assertIn('Djakarta', html)

  def test_places_without_others_come_first(self):
    # Mostly towns still waiting for a parent: on top, where they get attention.
    Content.objects.get(name='Haven').places.add(self.djakarta)
    html = self.html('/places/')
    self.assertLess(html.index('Djakarta'), html.index('Nederlandsch-Indië'))

  def test_in_the_menu(self):
    self.assertIn('href=/places/', self.html('/tags/', self.client_for(self.owner)))
    self.assertNotIn('href=/places/', self.html('/tags/'))                 # signed out: not advertised


class PlaceDetailTests(PlaceTestCase):
  """places/<token>/<slug>/ (PlaceDetailView): only what the viewer may see."""

  def test_shows_visible_content_and_events_only(self):
    html = self.html(self.batavia.get_absolute_url())
    self.assertIn('Haven', html)
    self.assertNotIn('Geheim', html)
    self.assertIn('Pieter', html)
    self.assertNotIn('Verborgen', html)                                    # a hidden person's event isn't listed
    self.assertIn(f'href={self.java.get_absolute_url()}>Java</a>', html)  # the path

  def test_sub_places_tree(self):
    html = self.html(self.indie.get_absolute_url())
    self.assertIn('Places in Nederlandsch-Indië', html)
    self.assertIn('Batavia', html)                                         # through Java, which is empty itself
    self.assertNotIn('Bandoeng', html)

  def test_token_and_old_slug_redirect(self):
    self.assertRedirects(self.client.get(f'/places/{self.batavia.token}/'), self.batavia.get_absolute_url(), status_code=301)
    old = self.batavia.get_absolute_url()
    self.batavia.name = 'Jacatra'
    self.batavia.save()
    self.assertEqual(self.batavia.slug, 'jacatra')                         # follows the name
    self.assertRedirects(self.client.get(old), self.batavia.get_absolute_url(), status_code=301)

  def test_place_names_link_to_their_page(self):
    html = self.html(self.public.get_absolute_url())
    self.assertIn(f'href={self.batavia.get_absolute_url()}>Batavia</a>', html)


class PlaceEditTests(PlaceTestCase):
  """Edit mode: blocks (Place.api_edit_forms), the parent picker, alternatives."""

  def setUp(self):
    super().setUp()
    self.editor = self.user('editor', 'change_place', 'add_place')
    self.client = self.client_for(self.editor, edit=True)

  def save_parent(self, place, parent, client=None):
    place.refresh_from_db()
    return (client or self.client).post(f'/api/place/{place.token}/form/parent/', {
      '_modified': place.date_modified.isoformat(), 'parent-parent': parent.token if parent else '',
    })

  def test_page_has_editable_blocks(self):
    html = self.html(self.batavia.get_absolute_url())
    for block in ('parent', 'name', 'alias', 'description'):
      self.assertIn(f'data-cmnsd-edit-url=/api/place/{self.batavia.token}/form/{block}/', html)
    self.assertIn('value=alternatives', html)                              # the alternatives picker

  def test_parent_form_is_a_picker_without_the_place_and_its_sub_places(self):
    html = self.client.get(f'/api/place/{self.java.token}/form/parent/').json()['html'].replace('"', '')
    self.assertIn('data-cmnsd-picker=place', html)
    self.assertIn(f'name=parent-parent type=hidden value={self.indie.token}>', html)   # the token, not the pk
    self.assertIn('Nederlandsch-Indië</span>', html)                       # the current choice by name
    for token in (self.java.token, self.batavia.token, self.bandoeng.token):
      self.assertIn(token, html.split('data-picker-exclude=')[1].split(' ')[0])

  def test_set_and_clear_the_parent(self):
    self.assertEqual(self.save_parent(self.djakarta, self.java).status_code, 200)
    self.assertEqual(Place.objects.get(pk=self.djakarta.pk).parent, self.java)
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.djakarta.pk), change_message__startswith='Changed').exists())
    self.assertEqual(self.save_parent(self.djakarta, None).status_code, 200)
    self.assertIsNone(Place.objects.get(pk=self.djakarta.pk).parent)

  def test_no_loops(self):
    response = self.save_parent(self.indie, self.batavia)
    self.assertEqual(response.status_code, 400)
    self.assertIn('parent', response.json()['errors']['validation'])
    self.assertEqual(self.save_parent(self.java, self.java).status_code, 400)
    self.assertIsNone(Place.objects.get(pk=self.indie.pk).parent)

  def test_new_parent_from_the_picker(self):
    self.djakarta.refresh_from_db()
    post = lambda name: self.client.post(f'/api/place/{self.djakarta.token}/form/parent/', {
      '_modified': Place.objects.get(pk=self.djakarta.pk).date_modified.isoformat(), 'parent-parent': '', 'parent-parent__new': name,
    })
    self.assertIn('data-picker-create=', self.client.get(f'/api/place/{self.djakarta.token}/form/parent/').json()['html'].replace('"', ''))
    self.assertEqual(post('Republik Indonesia').status_code, 200)
    new = Place.objects.get(name='Republik Indonesia')
    self.assertEqual(Place.objects.get(pk=self.djakarta.pk).parent, new)
    self.assertEqual(post('java').status_code, 200)                               # an existing name: that place, not a new one
    self.assertEqual(Place.objects.get(pk=self.djakarta.pk).parent, self.java)
    self.assertEqual(Place.objects.filter(name__iexact='java').count(), 1)

  def test_alternatives_are_both_ways(self):
    import json
    response = self.client.post(f'/api/place/{self.batavia.token}/link/', json.dumps({'relation': 'alternatives', 'token': self.djakarta.token}), content_type='application/json')
    self.assertEqual(response.status_code, 200)
    self.assertIn('Djakarta', response.json()['html'])
    self.assertIn(self.batavia, self.djakarta.alternatives.all())
    self.assertIn('Batavia', self.html(self.djakarta.get_absolute_url(), Client()))   # on both pages, also signed out
    self.client.post(f'/api/place/{self.batavia.token}/unlink/', json.dumps({'relation': 'alternatives', 'token': self.djakarta.token}), content_type='application/json')
    self.assertFalse(self.djakarta.alternatives.exists())

  def test_needs_change_place(self):
    reader = self.user('reader', 'change_content')                        # may edit, but not places
    client = self.client_for(reader, edit=True)
    self.assertEqual(self.save_parent(self.djakarta, self.java, client).status_code, 403)
    self.assertNotIn('/form/parent/', self.html(self.batavia.get_absolute_url(), client))


class PlaceBreadcrumbTests(TestCase):
  """A place's page always leads back: Places, then the places it lies in."""

  def test_back_to_the_list(self):
    from django.contrib.auth import get_user_model
    from django.test import Client
    from places.models import Place
    user = get_user_model().objects.create(username='a')
    user.save()
    indie = Place.objects.create(name='Nederlandsch-Indië', user=user)
    java = Place.objects.create(name='Java', parent=indie, user=user)
    client = Client()
    client.force_login(user)
    for place in (indie, java):
      self.assertIn('href=/places/', client.get(place.get_absolute_url()).content.decode().replace('"', ''))
