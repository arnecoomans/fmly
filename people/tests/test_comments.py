import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from core.models import Comment
from people.models import Person


class PersonCommentTests(TestCase):
  """Comments on a person: the same thread and API actions as content,
  in a collapsible section (key person.comments)."""

  def setUp(self):
    User = get_user_model()
    self.member = User.objects.create(username='member')
    self.member.user_permissions.add(Permission.objects.get(codename='add_comment'))
    self.person = Person.objects.create(given_name='Eric', user=self.member, status='p', visibility='p')
    self.client.force_login(self.member)

  def html(self, client=None):
    return (client or self.client).get(self.person.get_absolute_url()).content.decode().replace('"', '')

  def comment(self, text, visibility='c'):
    return Comment.objects.create(target=self.person, user=self.member, content=text, status='p', visibility=visibility)

  def test_add_comment_on_person_through_the_api(self):
    response = self.client.post(f'/api/person/{self.person.token}/add_comment/', json.dumps({'content': 'Opa!'}),
                                content_type='application/json')
    self.assertEqual(response.status_code, 200)
    self.assertIn('Opa!', response.json()['html'])
    self.assertEqual(self.person.comments.get().content, 'Opa!')

  def test_section_is_collapsible_with_count(self):
    self.comment('Eerste')
    html = self.html()
    self.assertIn('data-cmnsd-section=person.comments open', html)
    self.assertIn('Eerste', html)

  def test_closed_section_loads_through_the_api(self):
    self.comment('Eerste')
    self.client.post('/ui/section/', json.dumps({'key': 'person.comments', 'open': False}), content_type='application/json')
    html = self.html()
    self.assertNotIn('Eerste', html)
    self.assertIn('data-field=get_comments data-load-on-open=true', html)
    fields = self.client.get(f'/api/person/{self.person.token}/get_comments/').json()['fields']
    self.assertIn('Eerste', fields['get_comments'])
    self.assertIn('data-cmnsd-action=add_comment', fields['get_comments'].replace('"', ''))

  def test_empty_thread_still_offers_the_form_when_signed_in(self):
    html = self.html()
    # Foldable at 0 too: its body (the form) is there even without comments.
    self.assertIn('data-cmnsd-section=person.comments', html)
    self.assertIn('data-cmnsd-action=add_comment', html)

  def test_other_empty_sections_have_no_toggle(self):
    self.assertNotIn('data-cmnsd-section=person.events', self.html())   # nothing in it: no toggle

  def test_signed_out_visitor_sees_public_comments_only_and_no_form(self):
    self.comment('Voor iedereen', visibility='p')
    self.comment('Alleen leden')
    html = self.html(Client())
    self.assertIn('Voor iedereen', html)
    self.assertNotIn('Alleen leden', html)
    self.assertNotIn('add_comment', html)
    self.assertNotIn('data-cmnsd-section', html)   # visitors: plain sections

  def test_signed_out_visitor_without_public_comments_gets_muted_header(self):
    self.comment('Alleen leden')
    html = self.html(Client())
    self.assertIn('page-section--empty', html)
    self.assertNotIn('Alleen leden', html)
