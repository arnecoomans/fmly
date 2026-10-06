from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from content.models import Content
from core.models import Tag
from people.models import Person


class TagPageTests(TestCase):
  """tags/<token>/<slug>/ (core.views.TagDetailView)."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    self.collection = Tag.objects.create(name='Collection', user=self.user, status='p', visibility='c')
    self.tag = Tag.objects.create(name='Krangan 81', parent=self.collection, user=self.user, status='p', visibility='c',
                                  description='Door de jaren heen')
    item = lambda name, year, **f: Content.objects.create(name=name, year=year, kind='photo', user=self.user,
                                                         status='p', visibility=f.pop('visibility', 'c'), **f)
    self.old = item('Krangan 1992', 1992)
    self.new = item('Krangan 2010', 2010)
    other = get_user_model().objects.create(username='other')
    self.secret = item('Krangan privé', 2000, visibility='q')      # private to its owner...
    Content.objects.filter(pk=self.secret.pk).update(user=other)   # ...who isn't the viewer
    for c in (self.old, self.new, self.secret):
      c.tags.add(self.tag)

  def page(self, url=None, client=None):
    return (client or self.client).get(url or self.tag.get_absolute_url())

  def test_shows_context_and_visible_items(self):
    response = self.page()
    self.assertContains(response, 'Door de jaren heen')
    self.assertContains(response, 'Collection')
    self.assertEqual({i.name for i in response.context['items']}, {'Krangan 1992', 'Krangan 2010'})

  def test_tagged_part_shows_as_its_whole(self):
    back = Content.objects.create(name='Achterkant', user=self.user, status='p', visibility='c')
    self.old.tags.remove(self.tag)
    back.tags.add(self.tag)
    self.old.make_parts_of([back])
    self.assertIn('Krangan 1992', [i.name for i in self.page().context['items']])

  def test_parent_page_lists_children(self):
    self.assertEqual([t.name for t in self.page(self.collection.get_absolute_url()).context['children']], ['Krangan 81'])

  def test_people_with_the_tag(self):
    eric = Person.objects.create(given_name='Eric', user=self.user, status='p', visibility='c')
    eric.tags.add(self.tag)
    self.assertEqual(list(self.page().context['people']), [eric])

  def test_token_url_redirects_and_hidden_tag_404s(self):
    self.assertRedirects(self.page(f'/tags/{self.tag.token}/'), self.tag.get_absolute_url(), status_code=301)
    self.assertEqual(self.page(client=Client()).status_code, 404)   # community tag, signed out

  def test_chips_link_to_the_tag_page(self):
    html = self.client.get(self.new.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'class=tag href={self.tag.get_absolute_url()}', html)


class TagListTests(TestCase):
  """/tags/ (core.views.TagListView) and the content count on tag chips in
  a list (core/tags.py) - TagPageTests' setUp: Collection > Krangan 81
  with 2 visible items and 1 private one."""
  setUp = TagPageTests.setUp
  page = TagPageTests.page

  def overview(self, client=None):
    return (client or self.client).get('/tags/')

  def test_groups_children_with_counts(self):
    response = self.overview()
    [group] = response.context['groups']
    self.assertEqual(group.name, 'Collection')
    self.assertEqual([(t.name, t.content_count) for t in group.listed_children], [('Krangan 81', 2)])  # not the private one
    self.assertRegex(response.content.decode().replace('"', ''), r'Krangan 81 <span class=tag__count>2</span>')

  def test_loose_tags_and_empty_tags_left_out(self):
    boek = Tag.objects.create(name='boek', user=self.user, status='p', visibility='c')
    Tag.objects.create(name='leeg', user=self.user, status='p', visibility='c')     # nothing in it
    self.new.tags.add(boek)
    loose = self.overview().context['loose']
    self.assertEqual([(t.name, t.content_count) for t in loose], [('boek', 1)])

  def test_whole_counted_once_when_parts_carry_the_tag(self):
    back = Content.objects.create(name='Achterkant', user=self.user, status='p', visibility='c')
    back.tags.add(self.tag)
    self.old.make_parts_of([back])       # old: tagged itself and through its part
    [group] = self.overview().context['groups']
    self.assertEqual(group.listed_children[0].content_count, 2)

  def test_signed_out_sees_only_public(self):
    Tag.objects.filter(pk__in=[self.collection.pk, self.tag.pk]).update(visibility='p')
    Content.objects.filter(pk=self.old.pk).update(visibility='p')
    [group] = self.overview(Client()).context['groups']
    self.assertEqual(group.listed_children[0].content_count, 1)

  def test_child_tags_on_a_tag_page_show_counts(self):
    html = self.page(self.collection.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('Krangan 81 <span class=tag__count>2</span>', html)

  def test_chips_on_an_item_and_a_person_show_counts(self):
    html = self.client.get(self.new.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('Krangan 81 <span class=tag__count>2</span>', html)
    eric = Person.objects.create(given_name='Eric', user=self.user, status='p', visibility='c')
    eric.tags.add(self.tag)
    html = self.client.get(eric.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('Krangan 81 <span class=tag__count>2</span>', html)


class DraftTagTests(TestCase):
  """A concept tag is seen only by its creator and staff - and marked
  wherever it shows (tag/tag.html, the tag page, the overview)."""
  setUp = TagPageTests.setUp
  page = TagPageTests.page

  def make_draft(self, owner):
    draft = Tag.objects.create(name='Werktitel', user=owner, status='c', visibility='c')
    self.new.tags.add(draft)
    return draft

  def client_for(self, user):
    client = Client()
    user.save()
    client.force_login(user)
    return client

  def html(self, url, client=None):
    return (client or self.client).get(url).content.decode().replace('"', '')

  def test_creator_sees_it_marked(self):
    draft = self.make_draft(self.user)
    html = self.html(self.new.get_absolute_url())
    self.assertRegex(html, r'class=tag tag--draft [^>]*href=' + draft.get_absolute_url())   # minifier reorders attributes
    self.assertIn('class=tag__status>concept<', html)
    self.assertIn('not published', self.html(draft.get_absolute_url()))
    self.assertIn('Werktitel', self.html('/tags/'))

  def test_other_members_dont_see_it(self):
    other = get_user_model().objects.create(username='writer')
    draft = self.make_draft(other)
    self.assertNotIn('Werktitel', self.html(self.new.get_absolute_url()))
    self.assertNotIn('Werktitel', self.html('/tags/'))
    self.assertEqual(self.page(draft.get_absolute_url()).status_code, 404)

  def test_staff_see_it_marked(self):
    other = get_user_model().objects.create(username='writer')
    staff = get_user_model().objects.create(username='staff', is_staff=True)
    self.make_draft(other)
    html = self.html(self.new.get_absolute_url(), self.client_for(staff))
    self.assertIn('tag--draft', html)

  def test_published_tag_not_marked(self):
    self.assertNotIn('tag--draft', self.html(self.new.get_absolute_url()))


class TagOrderTests(TestCase):
  """Chips on an item's page: most content first, then by name
  (core/tags.py by_count)."""
  setUp = TagPageTests.setUp

  def test_item_chips_by_count(self):
    small = Tag.objects.create(name='Aaa klein', user=self.user, status='p', visibility='c')
    big = Tag.objects.create(name='Zzz groot', user=self.user, status='p', visibility='c')
    self.new.tags.add(small, big)
    self.old.tags.add(big)
    html = self.client.get(self.new.get_absolute_url()).content.decode()
    order = [name for name in ('Krangan 81', 'Zzz groot', 'Aaa klein') if name in html]
    self.assertEqual(sorted(order, key=html.index), ['Krangan 81', 'Zzz groot', 'Aaa klein'])   # 2, 2, 1 - ties by name
