from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Tag
from people.models import Person


class PersonDetailAccessTests(TestCase):
  """The detail page applies status as well as visibility - the same as
  the People list and the API (cmnsd filter_accessible)."""

  def setUp(self):
    User = get_user_model()
    self.owner = User.objects.create(username='owner')
    self.member = User.objects.create(username='member')
    self.staff = User.objects.create(username='staff', is_staff=True)

  def person(self, status):
    return Person.objects.create(given_name='Eric', last_name=status, user=self.owner, status=status, visibility='c')

  def status_for(self, user, person):
    self.client.force_login(user)
    return self.client.get(person.get_absolute_url()).status_code

  def test_published_is_visible(self):
    self.assertEqual(self.status_for(self.member, self.person('p')), 200)

  def test_deleted_is_hidden_from_everyone(self):
    person = self.person('x')
    for user in (self.member, self.owner, self.staff):
      self.assertEqual(self.status_for(user, person), 404, user.username)

  def test_concept_only_for_owner_and_staff(self):
    person = self.person('c')
    self.assertEqual(self.status_for(self.member, person), 404)
    self.assertEqual(self.status_for(self.owner, person), 200)
    self.assertEqual(self.status_for(self.staff, person), 200)

  def test_revoked_only_for_staff(self):
    person = self.person('r')
    self.assertEqual(self.status_for(self.owner, person), 404)
    self.assertEqual(self.status_for(self.staff, person), 200)

  def test_get_tags_skips_deleted_tags(self):
    person = self.person('p')
    kept = Tag.objects.create(name='kept', user=self.owner, status='p', visibility='p')
    gone = Tag.objects.create(name='gone', user=self.owner, status='x', visibility='p')
    person.tags.add(kept, gone)
    self.assertEqual(list(person.get_tags()), [kept])


class FullNameLinkTests(TestCase):
  """person/functions/get_full_name.html opens and closes its link under
  the same condition - a stray </a> would close a surrounding link."""

  def render(self, person, **context):
    from django.template.loader import render_to_string
    from django.test import RequestFactory
    request = RequestFactory().get('/')
    request.user = get_user_model().objects.create(username=f'viewer{Person.objects.count()}')
    return render_to_string('person/functions/get_full_name.html', {'person': person, 'request': request, **context})

  def test_balanced_links(self):
    owner = get_user_model().objects.create(username='owner')
    for visibility, suppress in (('c', False), ('c', True), ('q', False)):
      person = Person.objects.create(given_name='Eric', user=owner, status='p', visibility=visibility)
      html = self.render(person, suppress_link=suppress)
      self.assertEqual(html.count('<a '), html.count('</a>'), (visibility, suppress))
