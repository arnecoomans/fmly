import json

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content


class PartsEditingTests(TestCase):
  """Editing parts on the page (content/parts.py, Content's parts actions,
  content/_parts_edit.html): permission, the one-level rule, numbering
  with variants, logging."""

  def setUp(self):
    self.editor = self.user('editor', perm='change_content')
    self.member = self.user('member')
    self.book = self.item('Burgerkampen')
    self.pages = [self.item(f'Pagina {n}') for n in range(1, 4)]
    self.book.make_parts_of(self.pages)          # 1, 2, 3
    self.loose = self.item('Losse foto')

  def user(self, name, perm=None):
    user = get_user_model().objects.create(username=name)
    if perm:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def item(self, name):
    return Content.objects.create(name=name, kind='photo', user=self.editor, status='p', visibility='c')

  def client_for(self, user):
    client = Client()
    client.force_login(user)
    return client

  def act(self, obj, action, data=None, user=None):
    client = self.client_for(user or self.editor)
    return client.post(f'/api/content/{obj.token}/{action}/', json.dumps(data or {}), content_type='application/json')

  def numbers(self):
    return [(part.name, part.position) for part in self.book.parts.order_by('position', 'pk')]

  # --- permission ------------------------------------------------------

  def test_member_without_permission_gets_403(self):
    response = self.act(self.book, 'add_part', {'token': self.loose.token}, user=self.member)
    self.assertEqual(response.status_code, 403)
    self.assertIsNone(Content.objects.get(pk=self.loose.pk).parent_id)

  def test_signed_out_gets_403(self):
    response = Client().post(f'/api/content/{self.book.token}/add_part/', '{}', content_type='application/json')
    self.assertEqual(response.status_code, 403)

  # --- add -------------------------------------------------------------

  def test_add_part_goes_last_and_is_logged(self):
    self.assertEqual(self.act(self.book, 'add_part', {'token': self.loose.token}).status_code, 200)
    self.assertEqual(self.numbers()[-1], ('Losse foto', 4))
    messages = list(LogEntry.objects.values_list('object_id', 'change_message'))
    self.assertIn((str(self.book.pk), 'Added part 4: Losse foto'), messages)
    self.assertIn((str(self.loose.pk), 'Became part 4 of Burgerkampen'), messages)

  def test_one_level_rules(self):
    other = self.item('Ander boek')
    other.make_parts_of([self.item('Blad')])
    cases = [
      (self.pages[0], {'token': self.loose.token}),   # add to a part
      (self.book, {'token': self.book.token}),        # itself
      (self.book, {'token': other.token}),            # an item with parts
      (other, {'token': self.pages[0].token}),        # a part of something else
      (self.book, {'token': 'nope'}),                 # unknown
    ]
    for whole, data in cases:
      with self.subTest(whole=whole.name, data=data):
        response = self.act(whole, 'add_part', data)
        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.json()['error'])

  def test_make_this_a_part_of_is_add_part_on_the_chosen_whole(self):
    self.act(self.book, 'add_part', {'token': self.loose.token})
    self.assertEqual(Content.objects.get(pk=self.loose.pk).parent_id, self.book.pk)

  # --- order -----------------------------------------------------------

  def test_move_swaps_number_groups(self):
    self.act(self.pages[2], 'move_part', {'direction': 'earlier'})
    self.assertEqual(self.numbers(), [('Pagina 1', 1), ('Pagina 3', 2), ('Pagina 2', 3)])

  def test_variants_move_together(self):
    self.act(self.pages[1], 'join_previous')        # 1, 1, 2
    self.assertEqual(self.numbers(), [('Pagina 1', 1), ('Pagina 2', 1), ('Pagina 3', 2)])
    self.act(self.pages[2], 'move_part', {'direction': 'earlier'})
    self.assertEqual(self.numbers(), [('Pagina 3', 1), ('Pagina 1', 2), ('Pagina 2', 2)])

  def test_separate_gives_its_own_number_again(self):
    self.act(self.pages[1], 'join_previous')
    self.act(self.pages[1], 'separate_part')
    self.assertEqual(self.numbers(), [('Pagina 1', 1), ('Pagina 2', 2), ('Pagina 3', 3)])

  def test_move_at_the_edge_changes_nothing(self):
    self.assertEqual(self.act(self.pages[0], 'move_part', {'direction': 'earlier'}).status_code, 200)
    self.assertEqual(self.numbers(), [('Pagina 1', 1), ('Pagina 2', 2), ('Pagina 3', 3)])

  def test_variant_of_the_whole_and_back(self):
    self.act(self.pages[0], 'toggle_variant')
    self.assertEqual(self.numbers(), [('Pagina 1', 0), ('Pagina 2', 1), ('Pagina 3', 2)])
    self.assertEqual(self.act(self.pages[0], 'move_part', {'direction': 'later'}).status_code, 400)
    self.act(self.pages[0], 'toggle_variant')
    self.assertEqual(self.numbers(), [('Pagina 2', 1), ('Pagina 3', 2), ('Pagina 1', 3)])

  def test_detach_renumbers_and_keeps_the_item(self):
    self.act(self.pages[0], 'detach_part')
    self.assertEqual(self.numbers(), [('Pagina 2', 1), ('Pagina 3', 2)])
    page = Content.objects.get(pk=self.pages[0].pk)
    self.assertEqual((page.parent_id, page.position, page.status), (None, 0, 'p'))

  # --- page ------------------------------------------------------------

  def page(self, obj, user=None, edit=True):
    client = self.client_for(user or self.editor)
    if edit:
      client.post('/ui/edit/', {'on': '1', 'next': '/'})
    return client.get(obj.get_absolute_url()).content.decode().replace('"', '')

  def test_editor_in_edit_mode_gets_the_editor(self):
    html = self.page(self.book)
    self.assertIn('data-cmnsd-action=add_part', html)
    self.assertIn('class=parts-edit__rows', html)
    self.assertNotIn('make this item a part of', html.lower())   # it has parts

  def test_loose_item_offers_both_pickers(self):
    html = self.page(self.loose).lower()
    self.assertIn('add a part', html)
    self.assertIn('make this item a part of', html)

  def test_no_editor_without_edit_mode_or_permission(self):
    self.assertNotIn('parts-edit', self.page(self.book, edit=False))
    self.assertNotIn('parts-edit', self.page(self.book, user=self.member, edit=False))

  def test_picker_format(self):
    response = self.client_for(self.editor).get('/api/content/?q=Losse&format=picker')
    html = response.json()['html'].replace('"', '')
    self.assertIn(f'data-picker-choose={self.loose.token}', html)
    self.assertNotIn('Pagina', html)   # parts aren't offered (wholes only)

  def test_no_parts_section_without_parts_outside_edit_mode(self):
    self.assertNotIn('content.parts', self.page(self.loose, edit=False))   # no parts: nothing shown
    self.assertIn('content.parts', self.page(self.book, edit=False))       # with parts: shown
    self.assertIn('content.parts', self.page(self.loose))                  # edit mode: there, to add parts
