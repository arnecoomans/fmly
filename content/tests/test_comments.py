import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content
from core.models import Comment


class CommentActionTests(TestCase):
  """POST api/<model>/<token>/<action>/ (cmnsd object_action) and the
  comment actions (core.models.Comment / CommentableMixin)."""

  def setUp(self):
    User = get_user_model()
    self.author = User.objects.create(username='author')
    self.other = User.objects.create(username='other')
    self.staff = User.objects.create(username='staff', is_staff=True)
    for user in (self.author, self.other, self.staff):
      user.user_permissions.add(Permission.objects.get(codename='add_comment'))
    self.item = Content.objects.create(name='Trouwfoto', user=self.author, status='p', visibility='c')

  def post(self, user, model, token, action, data=None):
    client = Client()
    if user:
      client.force_login(user)
    return client.post(f'/api/{model}/{token}/{action}/', json.dumps(data or {}), content_type='application/json')

  def add(self, user=None, text='Mooie foto!'):
    return self.post(user or self.author, 'content', self.item.token, 'add_comment', {'content': text})

  # --- dispatcher ---

  def test_add_comment_returns_rendered_row(self):
    response = self.add()
    self.assertEqual(response.status_code, 200)
    body = response.json()
    self.assertTrue(body['ok'])
    self.assertIn('Mooie foto!', body['html'])
    comment = Comment.objects.get()
    self.assertEqual((comment.status, comment.visibility, comment.target), ('p', 'c', self.item))

  def test_undeclared_action_is_404(self):
    self.assertEqual(self.post(self.author, 'content', self.item.token, 'delete').status_code, 404)

  def test_signed_out_is_403(self):
    self.assertEqual(self.post(None, 'content', self.item.token, 'add_comment', {'content': 'x'}).status_code, 403)

  def test_cannot_act_on_what_you_cannot_see(self):
    Content.objects.filter(pk=self.item.pk).update(visibility='q')  # private to its owner
    self.assertEqual(self.add(self.other).status_code, 404)

  def test_empty_or_too_long_is_400(self):
    self.assertEqual(self.add(text='   ').status_code, 400)
    self.assertEqual(self.add(text='x' * 5001).status_code, 400)
    self.assertEqual(Comment.objects.count(), 0)

  def test_get_still_reads_fields(self):
    client = Client()
    client.force_login(self.author)
    self.assertEqual(client.get(f'/api/content/{self.item.token}/add_comment/').status_code, 400)  # not a field

  def test_csrf_enforced(self):
    client = Client(enforce_csrf_checks=True)
    client.force_login(self.author)
    response = client.post(f'/api/content/{self.item.token}/add_comment/', '{"content": "x"}', content_type='application/json')
    self.assertEqual(response.status_code, 403)

  # --- edit / delete / hide ---

  def comment(self):
    self.add()
    return Comment.objects.get()

  def test_only_author_edits(self):
    comment = self.comment()
    self.assertEqual(self.post(self.other, 'comment', comment.token, 'edit_comment', {'content': 'hack'}).status_code, 403)
    self.assertEqual(self.post(self.staff, 'comment', comment.token, 'edit_comment', {'content': 'hack'}).status_code, 403)
    response = self.post(self.author, 'comment', comment.token, 'edit_comment', {'content': 'Beter zo'})
    self.assertEqual(response.status_code, 200)
    self.assertIn('Beter zo', response.json()['html'])

  def test_author_deletes_softly(self):
    comment = self.comment()
    self.assertEqual(self.post(self.other, 'comment', comment.token, 'delete_comment').status_code, 403)
    response = self.post(self.author, 'comment', comment.token, 'delete_comment')
    self.assertEqual(response.status_code, 200)
    self.assertNotIn('html', response.json())      # the row is removed client-side
    comment.refresh_from_db()
    self.assertEqual(comment.status, 'x')          # kept, not shown
    self.assertEqual(self.post(self.author, 'comment', comment.token, 'edit_comment', {'content': 'x'}).status_code, 404)

  def test_staff_hides_and_unhides(self):
    comment = self.comment()
    self.assertEqual(self.post(self.author, 'comment', comment.token, 'toggle_hidden').status_code, 403)
    self.assertEqual(self.post(self.staff, 'comment', comment.token, 'toggle_hidden').status_code, 200)
    comment.refresh_from_db()
    self.assertEqual(comment.status, 'r')
    self.post(self.staff, 'comment', comment.token, 'toggle_hidden')
    comment.refresh_from_db()
    self.assertEqual(comment.status, 'p')


class CommentThreadTests(TestCase):
  def setUp(self):
    User = get_user_model()
    self.member = User.objects.create(username='member')
    self.staff = User.objects.create(username='staff', is_staff=True)
    self.item = Content.objects.create(name='Photo', user=self.member, status='p', visibility='p')

  def comment(self, text, **fields):
    fields.setdefault('status', 'p')
    fields.setdefault('visibility', 'c')
    return Comment.objects.create(target=self.item, user=self.member, content=text, **fields)

  def page(self, user=None):
    client = Client()
    if user:
      client.force_login(user)
    return client.get(self.item.get_absolute_url()).content.decode()

  def test_visibility_of_comments(self):
    self.comment('Voor iedereen', visibility='p')
    self.comment('Voor familie en leden')
    self.comment('Verborgen door staf', status='r')
    self.comment('Verwijderd', status='x')
    anonymous, member, staff = self.page(), self.page(self.member), self.page(self.staff)
    self.assertIn('Voor iedereen', anonymous)
    self.assertNotIn('Voor familie en leden', anonymous)
    self.assertNotIn('comment-form', anonymous)
    self.assertIn('Voor familie en leden', member)
    self.assertNotIn('Verborgen door staf', member)
    self.assertIn('Verborgen door staf', staff)
    for html in (anonymous, member, staff):
      self.assertNotIn('Verwijderd', html)

  def test_no_thread_for_visitor_without_public_comments(self):
    self.comment('Alleen leden')
    self.assertNotIn('id="comments"', self.page().replace('id=comments', 'id="comments"'))

  def test_markdown_is_sanitized(self):
    self.comment('<script>alert(1)</script> [link](javascript:alert(2))', visibility='p')
    html = self.page()
    self.assertNotIn('<script>alert(1)', html)
    self.assertNotIn('javascript:alert(2)', html)


class CommentPermissionTests(TestCase):
  """Commenting needs core.add_comment (the Visitors group): an account
  without it reads the comments, but gets no form and the action refuses."""

  def test_without_permission(self):
    user = get_user_model().objects.create(username='lezer')
    user.save()
    from people.models import Person
    person = Person.objects.create(given_name='Eric', user=user, status='p', visibility='c')
    client = Client()
    client.force_login(user)
    response = client.post(f'/api/person/{person.token}/add_comment/', json.dumps({'content': 'Hoi'}), content_type='application/json')
    self.assertEqual(response.status_code, 403)
    self.assertFalse(Comment.objects.exists())
    fields = client.get(f'/api/person/{person.token}/get_comments/').json()['fields']
    self.assertNotIn('add_comment', fields['get_comments'])
