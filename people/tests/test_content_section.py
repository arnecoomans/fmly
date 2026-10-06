from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from content.models import Content
from people.models import Person


class PersonContentSectionTests(TestCase):
  def setUp(self):
    User = get_user_model()
    self.owner = User.objects.create(username='owner')
    self.member = User.objects.create(username='member')
    self.person = Person.objects.create(given_name='Eric', user=self.owner, status='p', visibility='c')

  def item(self, name, kind='photo', year=None, **fields):
    fields.setdefault('status', 'p')
    fields.setdefault('visibility', 'c')
    content = Content.objects.create(name=name, kind=kind, year=year, user=self.owner, **fields)
    content.people.add(self.person)
    return content

  def page(self):
    self.client.force_login(self.member)
    return self.client.get(self.person.get_absolute_url())

  def visible(self):
    request = RequestFactory().get('/')
    request.user = self.member
    return self.person.get_visible_content(request)

  def test_most_recently_added_first(self):
    from datetime import datetime, timezone
    for name, added in (('Oldest', 2022), ('Newest', 2026), ('Middle', 2024)):
      item = self.item(name, year=1950)
      Content.objects.filter(pk=item.pk).update(date_created=datetime(added, 1, 1, tzinfo=timezone.utc))
    self.assertEqual([item.name for item in self.visible()], ['Newest', 'Middle', 'Oldest'])

  def test_hidden_and_book_parts_left_out(self):
    book = self.item('Bushido', kind='book')
    self.item('Back cover', parent=book, position=1)
    self.item('Private scan', visibility='q')
    self.item('Draft', status='c')
    self.assertEqual([item.name for item in self.visible()], ['Bushido'])

  def test_filter_pills_per_kind_with_counts(self):
    self.item('Photo 1')
    self.item('Photo 2')
    self.item('Passport', kind='document')
    from people.templatetags.tags import kind_counts
    self.assertEqual([(k, n) for k, _, n in kind_counts(self.visible())], [('photo', 2), ('document', 1)])
    response = self.page()
    # The HTML minifier may drop attribute quotes - accept either form.
    html = response.content.decode().replace('"', '')
    self.assertIn('data-cmnsd-filter=#person-content-grid', html)
    self.assertIn('data-filter-value=document', html)

  def test_empty_section_has_no_toggle(self):
    html = self.page().content.decode().replace('"', '')
    self.assertNotIn('data-cmnsd-section=person.content', html)
    self.assertIn('page-section--empty', html)

  def test_other_sub_kind_not_shown(self):
    photo = self.item('Photo', year=1949)
    self.assertEqual(photo.sub_kind_display, '')
    self.assertNotContains(self.page(), '1949 · ')

  def test_sort_switch_and_keys(self):
    from content.templatetags.content_tags import date_sort_key
    self.item('Dated', year=1943)
    self.item('Undated')
    html = self.page().content.decode().replace('"', '')
    self.assertIn('data-cmnsd-sort=#person-content-grid', html)
    self.assertIn('data-sort-date=1943-00-00', html)
    self.assertIn('data-sort-added=', html)
    self.assertEqual(date_sort_key(Content(year=1943, month=5, day=14)), '1943-05-14')
    self.assertEqual(date_sort_key(Content()), '')

  def sort(self, value, client=None):
    import json
    return (client or self.client).post('/ui/sort/', json.dumps({'key': 'person.content', 'value': value}),
                                        content_type='application/json')

  def test_remembered_sort_is_rendered_by_the_server(self):
    from datetime import datetime, timezone
    for name, year, added in (('A 1930, added 2020', 1930, 2020), ('B 1990, added 2026', 1990, 2026)):
      item = self.item(name, year=year)
      Content.objects.filter(pk=item.pk).update(date_created=datetime(added, 1, 1, tzinfo=timezone.utc))
    self.client.force_login(self.member)
    first = lambda: [i.name for i in self.fresh_visible()][0]
    self.assertEqual(first(), 'B 1990, added 2026')     # default: recently added
    self.assertEqual(self.sort('date').status_code, 200)
    self.assertEqual(first(), 'A 1930, added 2020')     # remembered: chronologically
    import re
    html = self.page().content.decode().replace('"', '')
    date_button = re.search(r'<button[^>]*data-sort-key=date[^>]*>', html).group(0)
    self.assertIn('is-active', date_button)             # the page opens on the remembered choice
    self.sort('added')
    self.assertEqual(first(), 'B 1990, added 2026')

  def fresh_visible(self):
    """Like a real request: the user loaded fresh, so a Preferences row
    created since isn't hidden by a cached 'no preferences'."""
    request = RequestFactory().get('/')
    request.user = get_user_model().objects.get(pk=self.member.pk)
    return self.person.get_visible_content(request)

  def test_sort_not_stored_when_signed_out_or_invalid(self):
    from django.test import Client
    self.assertEqual(self.sort('date', client=Client()).status_code, 403)
    self.client.force_login(self.member)
    self.assertEqual(self.sort('../x').status_code, 400)
    self.sort('bogus')                                  # well-formed but unknown: stored, ignored when read
    request = RequestFactory().get('/')
    request.user = get_user_model().objects.get(pk=self.member.pk)
    self.assertEqual(self.person.content_sort(request), 'added')
