import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from events.models import Event
from places.models import Place
from people.models import Person, PersonRelation


class PersonEditTestCase(TestCase):
  def setUp(self):
    self.editor = self.user('editor', 'change_person', 'add_person', 'add_tag')
    self.client = self.client_for(self.editor, edit=True)
    self.father = self.person('Albert', 'Coomans')
    self.mother = self.person('Corry', 'Bake')
    self.son = self.person('Eric', 'Coomans')

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

  def person(self, given, last, **fields):
    return Person.objects.create(given_name=given, last_name=last, user=self.editor, status='p', visibility='c', **fields)

  def action(self, person, action, client=None, **data):
    return (client or self.client).post(f'/api/person/{person.token}/{action}/', json.dumps(data), content_type='application/json')

  def save(self, person, block, **fields):
    person.refresh_from_db()
    data = {'_modified': person.date_modified.isoformat(), **{f'{block}-{k}': v for k, v in fields.items()}}
    return self.client.post(f'/api/person/{person.token}/form/{block}/', data)


class PersonBlocksTests(PersonEditTestCase):
  """Edit blocks (Person.api_edit_forms) on the person's page."""

  def test_page_has_the_blocks_in_edit_mode(self):
    html = self.client.get(self.son.get_absolute_url()).content.decode().replace('"', '')
    for block in ('names', 'birth', 'death', 'gender', 'family_connection', 'visibility', 'status', 'biography'):
      self.assertIn(f'data-cmnsd-edit-name={block} ', html)
    html = self.client_for(self.editor).get(self.son.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('data-cmnsd-edit-name=birth ', html)                 # edit mode off, no birth: no row

  def test_names(self):
    response = self.save(self.son, 'names', given_name='Eric Albert', called_name='Eric', last_name='Coomans', married_name='', nickname='')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(Person.objects.get(pk=self.son.pk).given_name, 'Eric Albert')
    self.assertEqual(self.save(self.son, 'names', given_name='', called_name='', last_name='', married_name='', nickname='').status_code, 400)

  def test_birth_creates_the_event_with_its_place(self):
    medan = Place.objects.create(name='Medan', user=self.editor)
    response = self.save(self.son, 'birth', date_qualifier='exact', day='5', month='7', year='1946', place=medan.token)
    self.assertEqual(response.status_code, 200)
    birth = Person.objects.get(pk=self.son.pk).birth
    self.assertEqual((birth.year, birth.month, birth.day, birth.user), (1946, 7, 5, self.editor))
    self.assertEqual(list(birth.places.all()), [medan])
    self.assertEqual(list(birth.people.all()), [self.son])
    self.assertIn('Medan', response.json()['html'])
    # Saved again: the same event, not a second one.
    self.save(self.son, 'birth', date_qualifier='circa', day='', month='', year='1946', place=medan.token)
    self.assertEqual(Event.objects.filter(kind='birth', people=self.son).count(), 1)

  def test_an_empty_form_creates_no_event(self):
    self.assertEqual(self.save(self.son, 'death', date_qualifier='exact', day='', month='', year='', place='').status_code, 200)
    self.assertFalse(Event.objects.filter(kind='death').exists())

  def test_tags(self):
    self.assertEqual(self.action(self.son, 'link', relation='tags', name='Medan').status_code, 200)
    self.assertEqual(list(self.son.tags.values_list('name', flat=True)), ['Medan'])

  def test_needs_change_person(self):
    reader = self.client_for(self.user('reader', 'change_content'), edit=True)
    self.son.refresh_from_db()
    response = reader.post(f'/api/person/{self.son.token}/form/names/', {'_modified': self.son.date_modified.isoformat()})
    self.assertEqual(response.status_code, 403)
    self.assertEqual(self.action(self.son, 'add_relative', reader, relation='parent', token=self.father.token).status_code, 403)


class RelativesTests(PersonEditTestCase):
  """add_relative / remove_relative (people/relatives.py)."""

  def test_parents_partner_children(self):
    self.assertEqual(self.action(self.son, 'add_relative', relation='parent', token=self.father.token).status_code, 200)
    self.assertEqual(self.action(self.father, 'add_relative', relation='partner', token=self.mother.token).status_code, 200)
    self.assertEqual(self.action(self.mother, 'add_relative', relation='child', token=self.son.token).status_code, 200)
    self.assertEqual(set(self.son.get_parents()), {self.father, self.mother})
    self.assertEqual(list(self.mother.get_partners()), [self.father])
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.father.pk), change_message__startswith='Added as parent').exists())

  def test_rules(self):
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    self.assertEqual(self.action(self.son, 'add_relative', relation='parent', token=self.father.token).status_code, 400)   # twice
    self.assertEqual(self.action(self.son, 'add_relative', relation='partner', token=self.son.token).status_code, 400)     # themselves
    self.assertEqual(self.action(self.father, 'add_relative', relation='parent', token=self.son.token).status_code, 400)   # own ancestor
    self.assertEqual(self.action(self.father, 'add_relative', relation='partner', token=self.son.token).status_code, 400)  # parent as partner
    self.action(self.son, 'add_relative', relation='parent', token=self.mother.token)
    third = self.person('Derde', 'Ouder')
    response = self.action(self.son, 'add_relative', relation='parent', token=third.token)
    self.assertEqual(response.status_code, 400)
    self.assertIn('two parents', response.json()['error'])

  def test_only_people_the_editor_may_see(self):
    hidden = Person.objects.create(given_name='Verborgen', user=self.user('other'), status='p', visibility='q')
    self.assertEqual(self.action(self.son, 'add_relative', relation='parent', token=hidden.token).status_code, 400)

  def test_remove(self):
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    self.assertEqual(self.action(self.son, 'remove_relative', relation='parent', token=self.father.token).status_code, 200)
    self.assertFalse(PersonRelation.objects.exists())
    self.assertTrue(Person.objects.filter(pk=self.father.pk).exists())     # the person stays

  def test_family_edited_in_place(self):
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    html = self.client.get(f'/api/person/{self.son.token}/get_relationships/').json()['fields']['get_relationships'].replace('"', '')
    self.assertEqual(html.count('data-cmnsd-action=add_relative'), 3)     # a picker under parents, partners, children
    self.assertEqual(html.count('data-cmnsd-action=remove_relative'), 1)  # an "×" on the father's row
    self.assertNotIn('relatives-edit', html)                              # no separate panel
    self.assertIn(f'data-picker-new-dialog=/api/person/new/?relative_of={self.son.token} ', html)   # parent, partner: family as the son is
    self.assertIn(f'data-picker-new-dialog=/api/person/new/?child_of={self.son.token}&last_name=Coomans ', html)   # a child: other parent + family name

  def test_a_new_child_carries_the_married_name(self):
    self.mother.married_name = 'Coomans'
    self.mother.save()
    html = self.client.get(f'/api/person/{self.mother.token}/get_relationships/').json()['fields']['get_relationships'].replace('"', '')
    self.assertIn(f'/api/person/new/?child_of={self.mother.token}&last_name=Coomans ', html)   # not Bake, her own last name
    page = self.client.get(f'/people/new/?relation=child&of={self.mother.token}').content.decode().replace('"', '')
    self.assertIn('value=Coomans', page)


class PersonCreateTests(PersonEditTestCase):
  """people/new/ (PersonCreateView)."""

  def test_add_as_a_child(self):
    page = self.client.get(f'/people/new/?relation=child&of={self.father.token}&given_name=Jan').content.decode().replace('"', '')
    self.assertIn('Will be added as a child of Albert Coomans', page)
    self.assertIn('value=Coomans', page)                                 # the family name, prefilled
    response = self.client.post('/people/new/', {
      'given_name': 'Jan', 'last_name': 'Coomans', 'gender': 'm', 'family_connection': 'family', 'visibility': 'c',
      'relation': 'child', 'of': self.father.token,
    })
    jan = Person.objects.get(given_name='Jan')
    self.assertRedirects(response, f'{jan.get_absolute_url()}?open=birth')
    self.assertEqual((jan.status, jan.visibility, jan.user), ('p', 'c', self.editor))
    self.assertEqual(list(jan.get_parents()), [self.father])

  def test_needs_a_name_and_add_person(self):
    self.assertEqual(self.client.post('/people/new/', {'gender': 'x', 'family_connection': 'family', 'visibility': 'c'}).status_code, 200)
    self.assertEqual(Person.objects.count(), 3)
    self.assertEqual(self.client_for(self.user('reader')).get('/people/new/').status_code, 403)

  def test_pickers_offer_the_new_page(self):
    from content.models import Content
    item = Content.objects.create(name='Foto', kind='photo', user=self.editor, status='p', visibility='c')
    self.editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    html = self.client_for(get_user_model().objects.get(pk=self.editor.pk), edit=True).get(item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-picker-new-dialog=/api/person/new/ ', html)


class PersonCreateDialogTests(PersonEditTestCase):
  """api/person/new/ (cmnsd object_create, Person.api_create_form) - the
  "+ new person" dialog."""

  def test_form_prefilled_from_the_query(self):
    data = self.client.get('/api/person/new/?given_name=Jan&last_name=Coomans').json()
    html = data['html'].replace('"', '')
    self.assertIn('data-cmnsd-create-form', html)
    self.assertIn('value=Jan', html)
    self.assertIn('value=Coomans', html)
    self.assertIn('id_visibility', html)                                   # the same fields as /people/new/

  def test_create(self):
    response = self.client.post('/api/person/new/', {
      'given_name': 'Jan', 'last_name': 'Coomans', 'gender': 'm', 'family_connection': 'family', 'visibility': 'f',
    })
    self.assertEqual(response.status_code, 200)
    jan = Person.objects.get(given_name='Jan')
    self.assertEqual(response.json()['created'], {'token': jan.token, 'name': 'Jan Coomans', 'url': jan.get_absolute_url()})
    self.assertEqual((jan.status, jan.visibility, jan.user), ('p', 'f', self.editor))
    self.assertTrue(LogEntry.objects.filter(object_id=str(jan.pk), change_message='Created on the site').exists())
    # Then the picker links it, as for a chosen person.
    self.assertEqual(self.action(self.father, 'add_relative', relation='child', token=jan.token).status_code, 200)

  def test_errors_and_permissions(self):
    response = self.client.post('/api/person/new/', {'gender': 'x', 'family_connection': 'family', 'visibility': 'c'})
    self.assertEqual(response.status_code, 400)                            # no name
    self.assertIn('data-cmnsd-create-form', response.json()['html'])
    self.assertEqual(self.client_for(self.user('reader')).get('/api/person/new/').status_code, 403)
    self.assertEqual(Client().post('/api/person/new/', {}).status_code, 403)
    self.assertEqual(self.client.get('/api/place/new/').status_code, 404)  # nothing declared: nothing to create


class OtherParentTests(PersonEditTestCase):
  """Adding a child: the form offers the other parent - the partners of the
  parent this user may see - not set by default."""

  def setUp(self):
    super().setUp()
    self.action(self.father, 'add_relative', relation='partner', token=self.mother.token)
    self.hidden = Person.objects.create(given_name='Verborgen', user=self.user('other'), status='p', visibility='q')
    from people.models import PersonRelation
    PersonRelation.objects.create(person_from=self.father, person_to=self.hidden, relation_type='partner')

  def test_choices_are_the_visible_partners(self):
    html = self.client.get(f'/api/person/new/?child_of={self.father.token}').json()['html'].replace('"', '')
    self.assertIn('data-cmnsd-toggle-single', html)
    self.assertIn('Corry Bake', html)
    self.assertNotIn('Verborgen', html)                                    # a partner this user can't see
    self.assertNotIn('checked', html)                                       # none pressed: not set

  def test_no_choice_without_child_of(self):
    self.assertNotIn('other_parent', self.client.get('/api/person/new/').json()['html'])

  def test_dialog_links_the_other_parent(self):
    response = self.client.post('/api/person/new/', {
      'given_name': 'Jan', 'last_name': 'Coomans', 'gender': 'm', 'family_connection': 'family', 'visibility': 'c',
      'child_of': self.father.token, 'other_parent': self.mother.token,
    })
    self.assertEqual(response.status_code, 200)
    jan = Person.objects.get(given_name='Jan')
    self.assertEqual(list(jan.get_parents()), [self.mother])               # the picker links the father next
    self.assertEqual(self.action(self.father, 'add_relative', relation='child', token=jan.token).status_code, 200)
    self.assertEqual(set(jan.get_parents()), {self.father, self.mother})

  def test_not_set_links_nobody(self):
    self.client.post('/api/person/new/', {
      'given_name': 'Emma', 'gender': 'f', 'family_connection': 'family', 'visibility': 'c',
      'child_of': self.father.token,
    })
    self.assertTrue(Person.objects.filter(given_name='Emma').exists())
    self.assertEqual(list(Person.objects.get(given_name='Emma').get_parents()), [])

  def test_one_at_most(self):
    other = self.person('Tweede', 'Partner')
    self.action(self.father, 'add_relative', relation='partner', token=other.token)
    response = self.client.post('/api/person/new/', {
      'given_name': 'Twee', 'gender': 'x', 'family_connection': 'family', 'visibility': 'c',
      'child_of': self.father.token, 'other_parent': [self.mother.token, other.token],
    })
    self.assertEqual(response.status_code, 400)
    self.assertIn('one other parent at most', response.json()['html'])

  def test_page_links_both(self):
    self.client.post('/people/new/', {
      'given_name': 'Piet', 'gender': 'm', 'family_connection': 'family', 'visibility': 'c',
      'relation': 'child', 'of': self.father.token, 'child_of': self.father.token, 'other_parent': self.mother.token,
    })
    self.assertEqual(set(Person.objects.get(given_name='Piet').get_parents()), {self.father, self.mother})


class SuggestedParentTests(PersonEditTestCase):
  """With one parent known, the likely other parent before typing: that
  parent's partners, then a sibling's other parent (people/relatives.py)."""

  def html(self, person):
    return self.client.get(f'/api/person/{person.token}/get_relationships/').json()['fields']['get_relationships'].replace('"', '')

  def test_partner_of_the_known_parent(self):
    self.action(self.father, 'add_relative', relation='partner', token=self.mother.token)
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    html = self.html(self.son)
    self.assertIn('relative-suggestions', html)
    self.assertIn(f'name=token type=hidden value={self.mother.token}', html)
    from people.relatives import suggested_parents
    from django.test import RequestFactory
    request = RequestFactory().get('/')
    request.user = self.editor
    self.assertEqual(suggested_parents(self.son, request), [(self.mother, 'partner')])

  def test_a_siblings_other_parent(self):
    daughter = self.person('Anna', 'Coomans')
    self.action(daughter, 'add_relative', relation='parent', token=self.father.token)
    self.action(daughter, 'add_relative', relation='parent', token=self.mother.token)   # no partnership recorded
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    self.assertIn(f'value={self.mother.token}', self.html(self.son))

  def test_only_with_exactly_one_parent(self):
    self.action(self.father, 'add_relative', relation='partner', token=self.mother.token)
    self.assertNotIn('relative-suggestions', self.html(self.son))           # no parent: nothing to go on
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    self.action(self.son, 'add_relative', relation='parent', token=self.mother.token)
    self.assertNotIn('relative-suggestions', self.html(self.son))           # both known

  def test_never_a_hidden_person(self):
    hidden = Person.objects.create(given_name='Verborgen', user=self.user('other'), status='p', visibility='q')
    PersonRelation.objects.create(person_from=self.father, person_to=hidden, relation_type='partner')
    self.action(self.son, 'add_relative', relation='parent', token=self.father.token)
    self.assertNotIn(hidden.token, self.html(self.son))


class PersonAddressTests(PersonEditTestCase):
  """person/<token>/<slug>/ - the token finds the person; token-only and
  old person/<slug>/ addresses redirect (keeping the query)."""

  def test_canonical_and_redirects(self):
    url = self.son.get_absolute_url()
    self.assertEqual(url, f'/person/{self.son.token}/{self.son.slug}/')
    self.assertEqual(self.client.get(url).status_code, 200)
    self.assertRedirects(self.client.get(f'/person/{self.son.slug}/'), url, status_code=301)            # old links in texts
    self.assertRedirects(self.client.get(f'/person/{self.son.token}/'), url, status_code=301)
    self.assertRedirects(self.client.get(f'/person/{self.son.token}/wrong/?open=birth'), f'{url}?open=birth', status_code=301)

  def test_hidden_and_private_stay_hidden(self):
    hidden = Person.objects.create(given_name='Verborgen', user=self.user('other'), status='p', visibility='q')
    self.assertEqual(self.client.get(f'/person/{hidden.slug}/').status_code, 404)
    self.assertEqual(self.client.get(f'/person/{hidden.token}/{hidden.slug}/').status_code, 404)
    private = self.person('Privé', 'Persoon', private=True)
    self.assertEqual(self.client.get(f'/person/{private.slug}/').status_code, 404)

  def test_pills_only_outside_edit_mode(self):
    html = self.client.get(self.son.get_absolute_url()).content.decode()
    self.assertNotIn('visibility-pill', html)                              # edit mode: the choices panel shows it
    html = self.client_for(self.editor).get(self.son.get_absolute_url()).content.decode()
    self.assertIn('visibility-pill', html)
