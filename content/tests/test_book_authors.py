from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from content.models import Content
from people.models import Person


class BookAuthorTests(TestCase):
  """BookContent.authors - authors as linked people (by hand), the text
  `author` as a fallback."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    self.writer = Person.objects.create(given_name='Jan', last_name='Cannoo', user=self.user,
                                        status='p', visibility='c', family_connection='outsider')
    self.book = Content.objects.create(name='Bushido', kind=Content.Kind.BOOK, user=self.user, status='p', visibility='c')
    self.detail = self.book.get_detail()
    self.detail.author = 'J.M. Cannoo'
    self.detail.save()

  def test_text_author_until_linked(self):
    self.assertContains(self.client.get(self.book.get_absolute_url()), 'J.M. Cannoo')
    self.detail.authors.add(self.writer)
    html = self.client.get(self.book.get_absolute_url()).content.decode()
    self.assertIn(self.writer.get_absolute_url(), html)
    self.assertNotIn('J.M. Cannoo', html)

  def test_book_on_the_authors_page_marked_author_once(self):
    self.detail.authors.add(self.writer)
    self.book.people.add(self.writer)                       # also "in it" - still listed once
    request = RequestFactory().get('/')
    request.user = get_user_model().objects.get(pk=self.user.pk)
    items = self.writer.get_visible_content(request)
    self.assertEqual([i.name for i in items], ['Bushido'])
    self.assertTrue(items[0].by_this_person)
    self.assertEqual(self.writer.count_visible_content(request), 1)
    self.assertContains(self.client.get(self.writer.get_absolute_url()), 'content-card__role')
