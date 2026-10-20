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
