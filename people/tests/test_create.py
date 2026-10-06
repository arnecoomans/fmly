import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from people.models import Person


class SimilarPeopleTests(TestCase):
  """people/similar/ (people/similar.py): possible duplicates of a new
  person while typing - every word in one of the name fields, only people
  this viewer may see, never by biography; "use this one" in the dialog."""

  def setUp(self):
    User = get_user_model()
    self.editor = User.objects.create(username='editor')
    self.editor.user_permissions.add(Permission.objects.get(codename='add_person'))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    make = lambda **f: Person.objects.create(user=self.editor, status='p', visibility='c', **f)
    self.willem = make(given_name='Willem Johan Alexander', last_name='Bake')
    make(given_name='Willem', last_name='Coomans')
    make(given_name='Jan', last_name='Jansen', biography='Werkte met Willem Bake.')
    Person.objects.create(given_name='Willem', last_name='Bake', user=User.objects.create(username='x'), status='p', visibility='q')

  def similar(self, **names):
    response = self.client.get('/people/similar/', names)
    self.assertEqual(response.status_code, 200)
    return response.json()['html'].replace('"', '')

  def test_every_word_in_a_name(self):
    html = self.similar(given_name='Willem', last_name='Bake')
    self.assertIn('Willem Johan Alexander', html)
    self.assertNotIn('Coomans', html)       # only one of the words
    self.assertNotIn('Jansen', html)        # by biography: no
    self.assertIn('1 person with these names', html)   # the hidden Willem Bake isn't counted
    self.assertNotIn('use this one', html.lower())     # on the page: links only

  def test_too_short_and_nothing(self):
    self.assertEqual(self.similar(given_name='Wi').strip(), '')
    self.assertEqual(self.similar(last_name='Zzyzx').strip(), '')

  def test_dialog_offers_the_existing_person(self):
    html = self.client.get('/people/similar/', {'last_name': 'Bake', 'dialog': '1'}).json()['html']
    self.assertIn('data-cmnsd-dialog-answer', html)
    self.assertIn(self.willem.token, html)

  def test_needs_add_person(self):
    reader = get_user_model().objects.create(username='reader')
    reader.save()
    client = Client()
    client.force_login(reader)
    self.assertEqual(client.get('/people/similar/', {'last_name': 'Bake'}).status_code, 403)

  def test_the_forms_ask_for_it(self):
    page = self.client.get('/people/new/').content.decode().replace('"', '')
    self.assertIn('data-cmnsd-hint=/people/similar/>', page)
    dialog = self.client.get('/api/person/new/').json()['html'].replace('"', '')
    self.assertIn('data-cmnsd-hint=/people/similar/?dialog=1', dialog)


class SplitTypedNameTests(TestCase):
  """A picker's "+ new person" sends the whole search as ?given_name=:
  the form splits off the last name (people/names.py) - a known name
  first (only of people this viewer may see), then a particle, then the
  last word."""

  def setUp(self):
    User = get_user_model()
    self.editor = User.objects.create(username='editor')
    self.editor.user_permissions.add(Permission.objects.get(codename='add_person'))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    Person.objects.create(given_name='Anna', last_name='Bake Coomans', user=self.editor, status='p', visibility='c')
    Person.objects.create(given_name='Geheim', last_name='Maria Schriek', user=get_user_model().objects.create(username='x'), status='p', visibility='q')

  def split(self, typed):
    from people.names import split_name
    from cmnsd.models.access import filter_accessible
    from django.test import RequestFactory
    request = RequestFactory().get('/')
    request.user = self.editor
    return split_name(typed, filter_accessible(Person.objects.all(), request))

  def test_known_last_name(self):
    self.assertEqual(self.split('Jan Willem bake coomans'), ('Jan Willem', 'bake coomans'))

  def test_particle(self):
    self.assertEqual(self.split('Emma Maria van der Wall'), ('Emma Maria', 'van der Wall'))

  def test_last_word(self):
    self.assertEqual(self.split('Johan Schriek'), ('Johan', 'Schriek'))
    self.assertEqual(self.split('Johan'), ('Johan', ''))

  def test_hidden_names_not_used(self):
    # "Maria Schriek" is only someone this viewer may not see: no hint of them.
    self.assertEqual(self.split('Anna Maria Schriek'), ('Anna Maria', 'Schriek'))

  def test_dialog_prefilled_split(self):
    html = self.client.get('/api/person/new/', {'given_name': 'Emma van der Wall'}).json()['html'].replace('"', '')
    self.assertIn('name=given_name value=Emma', html.replace('id=id_given_name ', ''))
    self.assertIn('van der Wall', html)

  def test_a_given_last_name_only_comes_off_the_end(self):
    html = self.client.get('/api/person/new/', {'given_name': 'Jan Coomans', 'last_name': 'Coomans'}).json()['html'].replace('"', '')
    self.assertNotIn('value=Jan Coomans', html)


class InheritedFamilyConnectionTests(TestCase):
  """A new parent, partner or child of someone is family as they are -
  not asked in the dialog, but said ("possibly family, like ...")."""

  def setUp(self):
    User = get_user_model()
    self.editor = User.objects.create(username='editor')
    self.editor.user_permissions.add(Permission.objects.get(codename='add_person'))
    self.editor.save()
    self.client = Client()
    self.client.force_login(self.editor)
    self.namesake = Person.objects.create(given_name='Pieter', last_name='Spreeuw', family_connection='possibly_family', user=self.editor, status='p', visibility='c')
    self.hidden = Person.objects.create(given_name='Geheim', family_connection='outsider', user=User.objects.create(username='x'), status='p', visibility='q')

  def dialog(self, **query):
    return self.client.get('/api/person/new/', query).json()['html'].replace('"', '')

  def test_dialog_inherits_and_says_so(self):
    html = self.dialog(relative_of=self.namesake.token)
    self.assertIn('name=family_connection type=hidden value=possibly_family', html)
    self.assertIn('possibly family, like Pieter Spreeuw', html)

  def test_child_of_inherits_too(self):
    self.assertIn('value=possibly_family', self.dialog(child_of=self.namesake.token))

  def test_without_a_relative_it_is_asked(self):
    self.assertIn('name=family_connection><option', self.dialog())

  def test_someone_hidden_is_not_inherited_from(self):
    html = self.dialog(relative_of=self.hidden.token)
    self.assertIn('name=family_connection><option', html)
    self.assertNotIn('Geheim', html)

  def test_created_with_the_inherited_connection(self):
    self.client.post('/api/person/new/', {'given_name': 'Anna', 'gender': 'x', 'visibility': 'c', 'relative_of': self.namesake.token, 'family_connection': 'possibly_family'})
    self.assertEqual(Person.objects.get(given_name='Anna').family_connection, 'possibly_family')
