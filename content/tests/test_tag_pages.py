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
    self.assertRegex(html, rf'<a [^>]*class=tag [^>]*href={self.tag.get_absolute_url()}')   # (attribute order: the minifier's)


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


class TagEditingTests(TestCase):
  """Edit mode on a tag's page (issue #458): name and description as
  editable blocks (Tag.api_edit_forms); a new name gives a new slug, the
  old address redirects."""

  def setUp(self):
    from django.contrib.auth.models import Permission
    self.editor = get_user_model().objects.create(username='editor')
    self.editor.user_permissions.add(Permission.objects.get(codename='change_tag'))
    self.editor.save()
    self.client.force_login(self.editor)
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.collection = Tag.objects.create(name='Collection', user=self.editor, status='p', visibility='c')
    self.tag = Tag.objects.create(name='Krangan 81', parent=self.collection, user=self.editor, status='p', visibility='c')

  def save(self, tag, block, **fields):
    tag.refresh_from_db()
    data = {'_modified': tag.date_modified.isoformat(), **{f'{block}-{k}': v for k, v in fields.items()}}
    return self.client.post(f'/api/tag/{tag.token}/form/{block}/', data)

  def test_blocks_on_the_page_for_an_editor_only(self):
    html = self.client.get(self.tag.get_absolute_url()).content.decode().replace('"', '')
    for block in ('name', 'description'):
      self.assertIn(f'data-cmnsd-edit-name={block} ', html)
    self.assertIn('/api/tag/', html)                                                # a pencil
    member = get_user_model().objects.create(username='member')
    client = Client()
    client.force_login(member)
    self.assertNotIn('/api/tag/', client.get(self.tag.get_absolute_url()).content.decode())

  def test_rename_gives_a_new_slug_and_the_old_address_redirects(self):
    old_url = self.tag.get_absolute_url()
    response = self.save(self.tag, 'name', name='Krangan 81 Jogja')
    self.assertEqual(response.status_code, 200)
    self.tag.refresh_from_db()
    self.assertEqual((self.tag.name, self.tag.slug), ('Krangan 81 Jogja', 'krangan-81-jogja'))
    self.assertEqual(response.json()['url'], self.tag.get_absolute_url())         # the page's address follows
    self.assertRedirects(self.client.get(old_url), self.tag.get_absolute_url(), status_code=301)

  def test_slug_unique_among_siblings_and_name_too(self):
    other = Tag.objects.create(name='Boot!', parent=self.collection, user=self.editor, status='p', visibility='c')
    self.save(self.tag, 'name', name='Boot')                                      # slug 'boot' is taken by 'Boot!'
    self.tag.refresh_from_db()
    self.assertEqual(self.tag.slug, 'boot-2')
    response = self.save(other, 'name', name='Boot')                              # the same name twice: refused
    self.assertEqual(response.status_code, 400)
    other.refresh_from_db()
    self.assertEqual(other.name, 'Boot!')

  def test_description_keeps_the_slug(self):
    Tag.objects.filter(pk=self.tag.pk).update(slug='krangan')                    # a slug from FMLY 2, not the name's
    self.save(self.tag, 'description', description='Door de jaren heen')
    self.tag.refresh_from_db()
    self.assertEqual((self.tag.description, self.tag.slug), ('Door de jaren heen', 'krangan'))

  def test_loose_end_tag_keeps_its_slug(self):
    from core.tags import LOOSE_END_SLUG, loose_end_tag
    tag = Tag.objects.create(name='Loose end', slug=LOOSE_END_SLUG, user=self.editor, status='p', visibility='c')
    self.save(tag, 'name', name='Nog uitzoeken')
    self.assertEqual(loose_end_tag(), tag)                                        # still found by its slug

  def test_move_to_another_parent_and_back_to_the_top(self):
    media = Tag.objects.create(name='Media', user=self.editor, status='p', visibility='c')
    self.assertEqual(self.save(self.tag, 'parent', parent=media.token).status_code, 200)
    self.tag.refresh_from_db()
    self.assertEqual((self.tag.parent, self.tag.slug), (media, 'krangan-81'))              # the slug stays
    html = self.client.get(self.tag.get_absolute_url()).content.decode()
    self.assertIn(media.get_absolute_url(), html)                                         # the path back up
    self.save(self.tag, 'parent', parent='')
    self.tag.refresh_from_db()
    self.assertIsNone(self.tag.parent)

  def test_move_refuses_a_loop_and_a_taken_name(self):
    below = Tag.objects.create(name='Jogja', parent=self.tag, user=self.editor, status='p', visibility='c')
    self.assertEqual(self.save(self.tag, 'parent', parent=below.token).status_code, 400)   # under its own child
    Tag.objects.create(name='Krangan 81', user=self.editor, status='p', visibility='c')    # the same name on top
    self.assertEqual(self.save(self.tag, 'parent', parent='').status_code, 400)
    self.tag.refresh_from_db()
    self.assertEqual(self.tag.parent, self.collection)

  def test_move_into_a_taken_slug(self):
    media = Tag.objects.create(name='Media', user=self.editor, status='p', visibility='c')
    Tag.objects.create(name='Krangan-81', parent=media, user=self.editor, status='p', visibility='c')   # slug krangan-81, another name
    self.save(self.tag, 'parent', parent=media.token)
    self.tag.refresh_from_db()
    self.assertEqual(self.tag.slug, 'krangan-81-2')

  def test_loose_end_tag_stays_on_top(self):
    from core.tags import LOOSE_END_SLUG
    tag = Tag.objects.create(name='Loose end', slug=LOOSE_END_SLUG, user=self.editor, status='p', visibility='c')
    self.assertEqual(self.save(tag, 'parent', parent=self.collection.token).status_code, 400)

  def new_parent(self, tag, name):
    tag.refresh_from_db()
    return self.client.post(f'/api/tag/{tag.token}/form/parent/', {
      '_modified': tag.date_modified.isoformat(), 'parent-parent': '', 'parent-parent__new': name,
    })

  def test_new_parent_from_the_picker(self):
    from django.contrib.auth.models import Permission
    self.editor.user_permissions.add(Permission.objects.get(codename='add_tag'))
    self.editor = get_user_model().objects.get(pk=self.editor.pk)                  # fresh permission cache
    Tag.objects.filter(pk=self.tag.pk).update(visibility='f')                       # a family-only tag...
    self.assertEqual(self.new_parent(self.tag, 'Media: Boeken').status_code, 200)   # two levels at once
    self.tag.refresh_from_db()
    self.assertEqual(self.tag.parent.display_name(), 'Media: Boeken')
    for tag in (self.tag.parent, self.tag.parent.parent):
      self.assertEqual((tag.status, tag.visibility), ('p', 'f'))                   # ...gets family-only parents, published
    self.new_parent(self.tag, 'collection')                                       # an existing tag: used, not made again
    self.tag.refresh_from_db()
    self.assertEqual(self.tag.parent, self.collection)
    self.assertEqual(Tag.objects.filter(name__iexact='collection').count(), 1)

  def test_new_parent_needs_add_tag(self):
    self.assertEqual(self.new_parent(self.tag, 'Iets nieuws').status_code, 400)
    self.assertFalse(Tag.objects.filter(name='Iets nieuws').exists())

