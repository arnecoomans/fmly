import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from content.models import Content
from people.models import Person, PersonRelation


class PersonSectionTests(TestCase):
  """Collapsible sections (cmnsd/section.html): state per section for all
  person pages, closed = not rendered, rendered on demand via the API."""

  def setUp(self):
    User = get_user_model()
    self.user = User.objects.create(username='viewer')
    self.person = Person.objects.create(given_name='Eric', user=self.user, status='p', visibility='c')
    self.other = Person.objects.create(given_name='Frank', user=self.user, status='p', visibility='c')
    parent = Person.objects.create(given_name='Albert', user=self.user, status='p', visibility='c')
    for child in (self.person, self.other):
      PersonRelation.objects.create(person_from=parent, person_to=child, relation_type=PersonRelation.RelationType.PARENT)
    item = Content.objects.create(name='Trouwfoto', user=self.user, status='p', visibility='c')
    item.people.add(self.person, self.other)
    self.client.force_login(self.user)

  def html(self, person=None):
    return self.client.get((person or self.person).get_absolute_url()).content.decode().replace('"', '')

  def close(self, key, is_open=False):
    return self.client.post('/ui/section/', json.dumps({'key': key, 'open': is_open}), content_type='application/json')

  def test_open_by_default_with_counts(self):
    html = self.html()
    self.assertIn('data-cmnsd-section=person.relationships open', html)
    self.assertIn('Albert', html)      # parent row rendered
    self.assertIn('Trouwfoto', html)   # content card rendered

  def test_closed_section_not_rendered_and_remembered_for_all_pages(self):
    self.assertEqual(self.close('person.content').status_code, 200)
    for person in (self.person, self.other):
      html = self.html(person)
      self.assertNotIn('Trouwfoto', html)
      self.assertIn('data-field=get_visible_content data-load-on-open=true', html)
      self.assertIn('Albert', html)    # other sections unaffected

  def test_closed_section_renders_through_the_api(self):
    self.close('person.content')
    response = self.client.get(f'/api/person/{self.person.token}/get_visible_content/')
    self.assertIn('Trouwfoto', response.json()['fields']['get_visible_content'])

  def test_reopen(self):
    self.close('person.relationships')
    self.close('person.relationships', is_open=True)
    self.assertIn('Albert', self.html())

  def test_signed_out_always_sees_everything(self):
    """Visitors get the default: plain sections, all rendered, no toggle -
    even if a signed-in user closed a section."""
    self.close('person.content')
    self.client.logout()
    Person.objects.filter(pk=self.person.pk).update(visibility='p')
    Content.objects.update(visibility='p')
    html = self.html()
    self.assertNotIn('data-cmnsd-section', html)
    self.assertIn('Parents', html)     # Albert is community: listed, name obfuscated
    self.assertIn('Trouwfoto', html)

  def test_signed_out_cannot_store_state(self):
    self.client.logout()
    self.assertEqual(self.close('person.events').status_code, 403)
    self.assertNotIn('cmnsd_sections', self.client.session)

  def test_bad_key_rejected(self):
    self.assertEqual(self.close('../etc').status_code, 400)

  def test_relationship_count_matches_rows(self):
    from django.test import RequestFactory
    request = RequestFactory().get('/')
    request.user = self.user
    self.assertEqual(self.person.count_relationships(request), 2)  # parent + sibling

  def test_saving_works_with_csrf_enforced(self):
    """As in the browser: the page sets the CSRF cookie, cmnsd.js sends it
    back as X-CSRFToken (sections.js)."""
    from django.test import Client
    client = Client(enforce_csrf_checks=True)
    client.force_login(self.user)
    client.get(self.person.get_absolute_url())
    token = client.cookies['csrftoken'].value
    body = json.dumps({'key': 'person.content', 'open': False})
    self.assertEqual(client.post('/ui/section/', body, content_type='application/json').status_code, 403)
    self.assertEqual(client.post('/ui/section/', body, content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code, 200)

  def test_csrf_meta_only_when_signed_in(self):
    """Signed out: no csrf-token meta tag, so no csrftoken cookie from it."""
    self.assertIn('csrf-token', self.html())
    self.client.logout()
    Person.objects.filter(pk=self.person.pk).update(visibility='p')
    response = self.client.get(self.person.get_absolute_url())
    self.assertNotIn('csrf-token', response.content.decode())
    self.assertNotIn('csrftoken', response.cookies)
