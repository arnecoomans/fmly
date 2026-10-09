from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from content.models import Content
from core.models import Comment
from people.models import Person


class CommentListTests(TestCase):
  """/comments/ (core.views.CommentListView, core/comments.py)."""

  def setUp(self):
    User = get_user_model()
    self.member = User.objects.create(username='member')
    self.other = User.objects.create(username='other')
    self.photo = Content.objects.create(name='Trouwfoto', user=self.member, status='p', visibility='c')
    self.person = Person.objects.create(given_name='Eric', user=self.member, status='p', visibility='c')
    self.client.force_login(self.member)

  def comment(self, target, text, **fields):
    fields.setdefault('status', 'p')
    fields.setdefault('visibility', 'c')
    return Comment.objects.create(target=target, user=self.member, content=text, **fields)

  def page(self, query='', client=None):
    return (client or self.client).get('/comments/' + query)

  def test_lists_comments_with_what_they_are_on_newest_first(self):
    self.comment(self.photo, 'Eerste')
    self.comment(self.person, 'Tweede')
    html = self.page().content.decode()
    self.assertLess(html.index('Tweede'), html.index('Eerste'))
    self.assertIn(self.photo.get_absolute_url(), html)
    self.assertIn(self.person.get_absolute_url(), html)

  def test_filter_by_target_kind(self):
    self.comment(self.photo, 'Over de foto')
    self.comment(self.person, 'Over Eric')
    self.assertNotIn('Over Eric', self.page('?on=content').content.decode())
    self.assertNotIn('Over de foto', self.page('?on=person').content.decode())

  def test_comment_on_something_you_cannot_see_is_left_out(self):
    secret = Content.objects.create(name='Geheim', user=self.member, status='p', visibility='q')  # private to member
    self.comment(secret, 'Op iets privés')
    self.comment(self.photo, 'Zichtbaar')
    viewer = Client()
    viewer.force_login(self.other)
    html = self.page(client=viewer).content.decode()
    self.assertIn('Zichtbaar', html)
    self.assertNotIn('Op iets privés', html)

  def test_private_person_left_out(self):
    Person.objects.filter(pk=self.person.pk).update(private=True)
    self.comment(self.person, 'Over een privé persoon')
    self.assertNotIn('Over een privé persoon', self.page().content.decode())

  def test_signed_in_only(self):
    response = self.page(client=Client())
    self.assertEqual(response.status_code, 302)
    self.assertIn('/accounts/login/', response['Location'])

  def test_grouped_under_what_they_are_on(self):
    self.comment(self.photo, 'Eerste over de foto')
    self.comment(self.photo, 'Tweede over de foto')
    self.comment(self.person, 'Over Eric')
    html = self.page().content.decode()
    self.assertEqual(html.count('comment-feed__group'), 2)       # two targets, two headers
    self.assertIn(f'{self.photo.get_absolute_url()}#comments', html.replace('"', ''))
    self.assertIn('comment-target__kind', html)

  def test_paginated(self):
    for i in range(35):
      self.comment(self.photo, f'Reactie {i}')
    first = self.page()
    self.assertEqual(len(first.context['comments']), 30)
    self.assertEqual(len(self.page('?page=2').context['comments']), 5)

  def test_only_on_what_the_viewer_may_see_and_never_on_revoked(self):
    """Issue #459: the target's own status and visibility count too."""
    private = Content.objects.create(name='Privé', user=self.other, status='p', visibility='q')
    revoked = Content.objects.create(name='Ingetrokken', user=self.member, status='r', visibility='c')
    self.comment(self.photo, 'Op de trouwfoto')
    self.comment(private, 'Op iets privés')
    self.comment(revoked, 'Op iets ingetrokkens')
    html = self.page().content.decode()
    self.assertIn('Op de trouwfoto', html)
    self.assertNotIn('Op iets privés', html)                       # the item: private to another
    self.assertNotIn('Op iets ingetrokkens', html)
    staff = get_user_model().objects.create(username='beheer', is_staff=True)
    client = Client()
    client.force_login(staff)
    self.assertNotIn('Op iets ingetrokkens', self.page(client=client).content.decode())   # staff neither: under review
