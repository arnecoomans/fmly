import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content, ContentPerson
from people.models import Person


class PersonRoleTests(TestCase):
  """How a person is on an item (ContentPerson, issue #471): a role menu per
  person in edit mode, the role under their name when reading, and pills by
  role on the person's page."""

  def setUp(self):
    self.editor = get_user_model().objects.create(username='rol', is_staff=True)
    for perm in ('change_content', 'change_person'):
      self.editor.user_permissions.add(Permission.objects.get(codename=perm))
    self.editor.save()
    self.reader = get_user_model().objects.create(username='lezer')
    self.reader.save()
    self.corry = Person.objects.create(given_name='Corry', user=self.editor, status='p', visibility='c')
    self.card = Content.objects.create(name='Ansichtkaart', kind='document', user=self.editor, status='p', visibility='c')
    self.photo = Content.objects.create(name='Strandfoto', kind='photo', user=self.editor, status='p', visibility='c')
    self.book = Content.objects.create(name='Rudimenta', kind='book', user=self.editor, status='p', visibility='c')
    for item in (self.card, self.photo, self.book):
      item.people.add(self.corry)

  def client_for(self, user, edit=True):
    client = Client()
    client.force_login(user)
    if edit:
      client.post('/ui/edit/', {'on': '1', 'next': '/'})
    return client

  def set_role(self, item, role, user=None):
    return self.client_for(user or self.editor).post(
      f'/api/content/{item.token}/set_person_role/', json.dumps({'person': self.corry.token, 'role': role}), content_type='application/json',
    )

  def role(self, item):
    return ContentPerson.objects.get(content=item, person=self.corry).role

  def test_a_new_link_has_no_role(self):
    self.assertEqual(self.role(self.card), '')                              # unknown - not a guess

  def test_set_and_clear(self):
    response = self.set_role(self.card, 'addressee')
    self.assertEqual(response.status_code, 200, response.content)
    self.assertEqual(self.role(self.card), 'addressee')
    self.assertIn('<option selected value=addressee>', response.json()['html'].replace('"', ''))   # the chip again, with its menu (the minifier orders attributes)
    self.set_role(self.card, '')
    self.assertEqual(self.role(self.card), '')

  def test_refusals(self):
    self.assertEqual(self.set_role(self.card, 'bystander').status_code, 400)
    self.assertEqual(self.set_role(self.book, 'creator').status_code, 400)  # a book's authors: on its detail
    self.assertEqual(self.set_role(self.card, 'subject', user=self.reader).status_code, 403)
    self.assertEqual(self.role(self.card), '')

  def test_shown_on_the_item(self):
    self.set_role(self.photo, 'depicted')
    reading = self.client_for(self.editor, edit=False).get(self.photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('person-row__link-role>depicted<', reading)
    editing = self.client_for(self.editor).get(self.photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-action=set_person_role', editing)
    book = self.client_for(self.editor).get(self.book.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('value=creator', book)

  def test_role_pills_on_the_person_page(self):
    self.set_role(self.photo, 'depicted')
    self.set_role(self.card, 'addressee')
    items = self.corry.get_visible_content(self.client_for(self.editor).get('/').wsgi_request)
    self.assertEqual({item.name: item.person_role for item in items}, {'Strandfoto': 'depicted', 'Ansichtkaart': 'addressee', 'Rudimenta': ''})
    from content.templatetags.content_tags import role_counts
    self.assertEqual([(role, count) for role, _label, count in role_counts(items)], [('addressee', 1), ('depicted', 1)])   # in the roles' order of weight

  def test_the_role_on_the_card(self):
    self.set_role(self.card, 'addressee')
    from content.templatetags.content_tags import card_role
    items = {item.name: item for item in self.corry.get_visible_content(self.client_for(self.editor).get('/').wsgi_request)}
    self.assertEqual(card_role(items['Ansichtkaart']), 'addressee')
    self.assertEqual(card_role(items['Strandfoto']), '')

  def test_possibly_depicted(self):
    self.assertEqual(self.set_role(self.photo, 'possibly_depicted').status_code, 200)
    reading = self.client_for(self.editor, edit=False).get(self.photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('person-row__link-role>possibly depicted<', reading)   # readers see the doubt


class SuggestedRoleTests(TestCase):
  """The role an item's kind suggests (content/roles.py SUGGESTED_ROLES):
  marked in the menu, set for everyone without one on request - never by
  itself."""

  def setUp(self):
    from content.models import PhotoContent, DocumentContent
    self.editor = get_user_model().objects.create(username='suggest', is_staff=True)
    self.editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    self.editor.save()
    self.eric = Person.objects.create(given_name='Eric', user=self.editor, status='p', visibility='c')
    self.herko = Person.objects.create(given_name='Herko', user=self.editor, status='p', visibility='c')
    self.portrait = Content.objects.create(name='Eric 22', kind='photo', user=self.editor, status='p', visibility='c')
    PhotoContent.objects.update_or_create(content=self.portrait, defaults={'photo_kind': 'portrait'})
    self.candid = Content.objects.create(name='Eric en Herko', kind='photo', user=self.editor, status='p', visibility='c')
    PhotoContent.objects.update_or_create(content=self.candid, defaults={'photo_kind': 'candid'})
    self.clipping = Content.objects.create(name='Oranje', kind='document', user=self.editor, status='p', visibility='c')
    DocumentContent.objects.update_or_create(content=self.clipping, defaults={'document_kind': 'newspaper'})
    for item in (self.portrait, self.candid, self.clipping):
      item.people.add(self.eric)
    self.candid.people.add(self.herko)
    self.client = Client()
    self.client.force_login(self.editor)

  def test_by_kind(self):
    for item, role in ((self.portrait, 'subject'), (self.candid, 'depicted'), (self.clipping, '')):
      self.assertEqual(Content.objects.get(pk=item.pk).suggested_person_role(), role)
    self.assertEqual(ContentPerson.objects.exclude(role='').count(), 0)      # never set by itself

  def test_apply(self):
    response = self.client.post(f'/api/content/{self.candid.token}/apply_suggested_roles/', '{}', content_type='application/json')
    self.assertEqual(response.status_code, 200, response.content)
    self.assertEqual(set(ContentPerson.objects.filter(content=self.candid).values_list('role', flat=True)), {'depicted'})
    nothing = self.client.post(f'/api/content/{self.clipping.token}/apply_suggested_roles/', '{}', content_type='application/json')
    self.assertEqual(nothing.status_code, 400)                                  # a newspaper suggests nothing

  def test_marked_in_the_menu_and_the_loose_end(self):
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    page = self.client.get(self.portrait.get_absolute_url()).content.decode()
    self.assertIn('subject (suggested)', page)
    loose = self.client.get('/dashboard/loose-ends/people-without-role/').content.decode()
    self.assertIn('All: depicted', loose)
    self.assertIn('Set: subject', loose)


class RelatedContentTests(TestCase):
  """Items that reach a person through their own events (Person.
  get_related_content): under Content, a heading of its own - not history,
  not what's linked to them already."""

  def setUp(self):
    from events.models import Event
    self.user = get_user_model().objects.create(username='related', is_staff=True)
    self.user.save()
    self.bob = Person.objects.create(given_name='Bob', user=self.user, status='p', visibility='c')
    self.voyage = Event.objects.create(kind='migration', year=1952, title='Per Oranje', user=self.user)
    self.voyage.people.add(self.bob)
    self.invasion = Event.objects.create(kind='historical', year=1942, title='Inval', user=self.user)
    self.invasion.people.add(self.bob)
    self.clipping = Content.objects.create(name='Oranje morgen in Amsterdam', kind='document', user=self.user, status='p', visibility='c')
    self.history = Content.objects.create(name='Inval Java', kind='document', user=self.user, status='p', visibility='c')
    self.linked = Content.objects.create(name='Paspoort', kind='document', user=self.user, status='p', visibility='c')
    self.voyage.content.add(self.clipping, self.linked)
    self.invasion.content.add(self.history)
    self.linked.people.add(self.bob)
    self.client = Client()
    self.client.force_login(self.user)

  def test_rules(self):
    request = self.client.get('/').wsgi_request
    related = self.bob.get_related_content(request)
    self.assertEqual([item.name for item in related], ['Oranje morgen in Amsterdam'])   # not history, not what's linked
    self.assertEqual(related[0].via, ['migration 1952'])
    from content.templatetags.content_tags import card_role
    self.assertEqual(card_role(related[0]), 'via migration 1952')

  def test_on_the_page(self):
    html = self.client.get(f'/api/person/{self.bob.token}/fields/?fields=get_visible_content', HTTP_ACCEPT='application/json')
    page = self.client.get(self.bob.page_url()).content.decode()
    self.assertIn('Related content', page + html.content.decode())


class FromPagesTests(TestCase):
  """A whole's page shows what its pages are linked to - people and events,
  each once with the pages - apart from its own links."""

  def test_people_and_events_of_its_pages(self):
    from events.models import Event
    user = get_user_model().objects.create(username='pages', is_staff=True)
    user.save()
    abraham = Person.objects.create(given_name='Abraham', user=user, status='p', visibility='c')
    almanac = Content.objects.create(name='Regeeringsalmanak', kind='book', year=1874, user=user, status='p', visibility='c')
    p1879 = Content.objects.create(name='Almanak 1879', kind='document', year=1879, parent=almanac, position=1, user=user, status='p', visibility='c')
    p1880 = Content.objects.create(name='Almanak 1880', kind='document', year=1880, parent=almanac, position=2, user=user, status='p', visibility='c')
    for page in (p1879, p1880):
      page.people.add(abraham)
    ContentPerson.objects.filter(content=p1879).update(role='subject')
    appointment = Event.objects.create(kind='appointment', title='Benoemd tot onderopziener', year=1879, user=user)
    appointment.content.add(p1879)
    client = Client()
    client.force_login(user)
    page = client.get(almanac.get_absolute_url()).content.decode()
    self.assertIn('on its pages', page)
    self.assertEqual(page.count('Benoemd tot onderopziener'), 1)              # once, under its pages
    self.assertIn('documented by its pages', page)
    self.assertIn('(subject)', page)
    self.assertIn('p. 1</a> (subject)', page)                                   # by page number, not its year
    self.assertNotIn('on its pages', client.get(p1879.get_absolute_url()).content.decode())   # a page doesn't show its siblings'
