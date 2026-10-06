from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content


class FieldBlockTests(TestCase):
  """Editable blocks on an item's page (cmnsd object_form,
  Content.api_edit_forms, cmnsd/edit/block.html + form.html): the name
  and the description."""

  def setUp(self):
    self.editor = self.user('editor', 'change_content')
    self.member = self.user('member')
    self.item = Content.objects.create(name='Foto', description='Oud', kind='photo', user=self.editor, status='p', visibility='c')

  def user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def client_for(self, user, edit=True):
    client = Client()
    client.force_login(user)
    if edit:
      client.post('/ui/edit/', {'on': '1', 'next': '/'})
    return client

  def url(self, block):
    return f'/api/content/{self.item.token}/form/{block}/'

  def open_form(self, block, client=None):
    return (client or self.client_for(self.editor)).get(self.url(block))

  def modified(self):
    return Content.objects.get(pk=self.item.pk).date_modified.isoformat()

  def post(self, block, data, client=None, modified=None):
    client = client or self.client_for(self.editor)
    return client.post(self.url(block), {'_modified': modified or self.modified(), **data})

  def test_form_and_save(self):
    form = self.open_form('description').json()['html'].replace('"', '')
    self.assertIn('name=description-description', form)       # prefixed per block
    self.assertIn('>\nOud</textarea>', form)                # (Django's leading newline - browsers drop it)
    response = self.post('description', {'description-description': 'Het huis aan de *Roemer Visscherlaan*'})
    self.assertEqual(response.status_code, 200)
    data = response.json()
    self.assertIn('<em>Roemer Visscherlaan</em>', data['html'])
    self.assertIn('Saved.', [m['text'] for m in data['messages']])
    self.assertEqual(Content.objects.get(pk=self.item.pk).description, 'Het huis aan de *Roemer Visscherlaan*')
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.item.pk), change_message__startswith='Changed description').exists())

  def test_rename_returns_the_new_address(self):
    data = self.post('name', {'name-name': 'Huize Yvonne'}).json()
    item = Content.objects.get(pk=self.item.pk)
    self.assertEqual(data['url'], item.get_absolute_url())
    self.assertIn('huize-yvonne', data['url'])

  def test_saved_over_a_newer_version_is_refused(self):
    stale = self.modified()
    Content.objects.filter(pk=self.item.pk).update(description='Iemand anders')
    item = Content.objects.get(pk=self.item.pk)
    item.save()                                              # bumps date_modified
    response = self.post('description', {'description-description': 'Mijn versie'}, modified=stale)
    self.assertEqual(response.status_code, 409)
    self.assertEqual(Content.objects.get(pk=self.item.pk).description, 'Iemand anders')

  def test_permission_and_unknown_block(self):
    self.assertEqual(self.open_form('name', self.client_for(self.member, edit=False)).status_code, 403)
    self.assertEqual(self.post('name', {'name-name': 'X'}, self.client_for(self.member, edit=False)).status_code, 403)
    self.assertEqual(self.open_form('nonexistent').status_code, 404)   # not an editable block

  def test_page_shows_pencils_only_in_edit_mode(self):
    html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'data-cmnsd-edit-url=/api/content/{self.item.token}/form/name/', html)
    self.assertIn(f'data-cmnsd-edit-url=/api/content/{self.item.token}/form/description/', html)
    plain = self.client_for(self.editor, edit=False).get(self.item.get_absolute_url()).content.decode()
    self.assertNotIn('data-cmnsd-edit-open', plain)

  def test_empty_description_is_editable(self):
    Content.objects.filter(pk=self.item.pk).update(description='')
    html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode()
    self.assertIn('No description yet.', html)
    self.assertNotIn('No description yet.', self.client_for(self.editor, edit=False).get(self.item.get_absolute_url()).content.decode())

  # --- the date block ----------------------------------------------------

  def date(self, **fields):
    data = {'date-date_qualifier': 'exact', 'date-day': '', 'date-month': '', 'date-year': ''}
    data.update({f'date-{key}': value for key, value in fields.items()})
    return self.post('date', data)

  def test_date_saves_and_shows(self):
    response = self.date(date_qualifier='circa', day='5', month='7', year='1968')
    self.assertEqual(response.status_code, 200)
    self.assertIn('ca. 5 Jul 1968', response.json()['html'])
    item = Content.objects.get(pk=self.item.pk)
    self.assertEqual((item.year, item.month, item.day, item.date_qualifier), (1968, 7, 5, 'circa'))

  def test_date_rules(self):
    cases = [
      ({'day': '31', 'month': '2', 'year': '1950'}, "That date doesn't exist."),
      ({'day': '5', 'year': '1950'}, 'A day needs a month.'),
      ({'month': '3'}, 'A month needs a year.'),
      ({'year': '0'}, 'Enter a year from 1 onwards.'),
    ]
    for fields, message in cases:
      with self.subTest(fields=fields):
        response = self.date(**fields)
        self.assertEqual(response.status_code, 400)
        self.assertIn(message, response.json()['html'])

  def test_no_year_means_exact_and_unknown(self):
    self.date(year='1950', date_qualifier='before')
    response = self.date(date_qualifier='before')            # year removed
    self.assertEqual(Content.objects.get(pk=self.item.pk).date_qualifier, 'exact')
    self.assertIn('unknown', response.json()['html'])

  # --- choices (saved on click) ---------------------------------------------

  def choose(self, block, field, value):
    return self.post(block, {f'{block}-{field}': value})

  def test_visibility_choice(self):
    response = self.choose('visibility', 'visibility', 'f')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(Content.objects.get(pk=self.item.pk).visibility, 'f')
    html = response.json()['html'].replace('"', '')
    self.assertRegex(html, r'class=choice-btn is-active[^>]*value=f|value=f[^>]*class=choice-btn is-active')
    self.assertNotIn('data-cmnsd-edit-open', html)            # a choice block has no pencil

  def test_deleting_goes_to_the_list(self):
    response = self.choose('status', 'status', 'x')
    data = response.json()
    self.assertEqual(data['redirect'], '/content/')
    self.assertNotIn('html', data)
    self.assertIn('deleted - it can be recovered in the admin', ' '.join(m['text'] for m in data['messages']))
    self.assertEqual(Content.objects.get(pk=self.item.pk).status, 'x')

  def test_photo_kind_edits_the_photo_details(self):
    self.assertEqual(self.choose('photo_kind', 'photo_kind', 'portrait').status_code, 200)
    self.assertEqual(Content.objects.get(pk=self.item.pk).photo_detail.photo_kind, 'portrait')
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.item.pk), change_message__contains='kind of photo').exists())

  def test_document_kind_and_language(self):
    Content.objects.filter(pk=self.item.pk).update(kind='document')
    item = Content.objects.get(pk=self.item.pk)
    item.ensure_detail()
    self.choose('language', 'language', 'en')
    self.choose('document_kind', 'document_kind', 'newspaper')
    detail = Content.objects.get(pk=self.item.pk).document_detail
    self.assertEqual((detail.language, detail.document_kind), ('en', 'newspaper'))

  def test_choices_panel_in_edit_mode_only_and_draft_marked(self):
    html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode()
    self.assertIn('content-detail__choices', html)
    self.assertIn('photo_kind-photo_kind', html)
    self.assertNotIn('document_kind', html)                   # a photo
    Content.objects.filter(pk=self.item.pk).update(status='c')
    plain = self.client_for(self.editor, edit=False).get(self.item.get_absolute_url()).content.decode()
    self.assertNotIn('content-detail__choices', plain)
    self.assertIn('not published', plain)

  def test_a_second_save_on_the_same_page_uses_the_new_version(self):
    client = self.client_for(self.editor)
    page_version = self.modified()                           # what every form on the page carries
    first = self.post('visibility', {'visibility-visibility': 'f'}, client, modified=page_version).json()
    self.assertNotEqual(first['modified'], page_version)     # the page updates its other forms to this
    second = self.post('status', {'status-status': 'c'}, client, modified=first['modified'])
    self.assertEqual(second.status_code, 200)
    stale = self.post('status', {'status-status': 'p'}, client, modified=page_version)
    self.assertEqual(stale.status_code, 409)                 # an old version is still refused

  # --- status as actions, kind ---------------------------------------------

  def action_values(self, user):
    from content.forms import ContentStatusForm
    item = Content.objects.get(pk=self.item.pk)
    return [action[0] for action in ContentStatusForm(instance=item).actions(user)]

  def test_status_actions_per_user(self):
    other = self.user('other', 'change_content')               # an editor, not the owner
    staff = self.user('staff', 'change_content')
    staff.is_staff = True
    staff.save()
    Content.objects.filter(pk=self.item.pk).update(status='c')
    self.assertEqual(self.action_values(self.editor), ['p', 'x'])       # owner: publish, delete
    self.assertEqual(self.action_values(other), ['p'])
    Content.objects.filter(pk=self.item.pk).update(status='p')
    self.assertEqual(self.action_values(self.editor), ['c', 'x'])       # back to draft, delete
    self.assertEqual(self.action_values(staff), ['c', 'r'])             # back to draft, revoke
    self.assertEqual(self.action_values(other), ['c'])
    Content.objects.filter(pk=self.item.pk).update(status='r')
    self.assertEqual(self.action_values(staff), ['p', 'x'])             # republish or delete - a review
    Content.objects.filter(pk=self.item.pk).update(status='p', user=staff)
    self.assertEqual(self.action_values(staff), ['c', 'r'])             # staff revoke their own too, never delete
    Content.objects.filter(pk=self.item.pk).update(status='c')
    self.assertEqual(self.action_values(staff), ['p', 'r'])

  def test_status_refuses_what_it_did_not_offer(self):
    other = self.user('other', 'change_content')
    response = self.post('status', {'status-status': 'x'}, self.client_for(other))   # not the owner
    self.assertEqual(response.status_code, 400)
    self.assertEqual(Content.objects.get(pk=self.item.pk).status, 'p')

  def test_status_block_shows_current_and_actions(self):
    html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertRegex(html, r'<span[^>]*edit-choices__current[^>]*>Published</span>')
    # a flow: (Back to draft) Published (Delete)
    self.assertRegex(html, r'Back to draft</button>\s*<span[^>]*edit-choices__current[^>]*>Published</span>\s*<button[^>]*>Delete')
    self.assertNotIn('>Revoked<', html)

  def test_kind_change_reloads_and_keeps_details(self):
    data = self.choose('kind', 'kind', 'document').json()
    self.assertTrue(data['reload'])
    item = Content.objects.get(pk=self.item.pk)
    self.assertEqual(item.kind, 'document')
    self.assertTrue(hasattr(item, 'document_detail'))
    self.assertTrue(hasattr(item, 'photo_detail'))             # the photo details stay
    html = self.client_for(self.editor).get(item.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('value=unknown', html)                     # 'unknown' isn't offered

  def test_empty_language_shows_as_not_set(self):
    Content.objects.filter(pk=self.item.pk).update(kind='document')
    Content.objects.get(pk=self.item.pk).ensure_detail()
    html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertRegex(html, r'name=language-language[^>]*>\s*<option selected value>—')

  # --- source, book details, suggestions ------------------------------------

  def make_book(self, publisher='', owner=None, visibility='c'):
    book = Content.objects.create(name='Boek', kind='book', user=owner or self.editor, status='p', visibility=visibility)
    book.ensure_detail()
    if publisher:
      type(book.book_detail).objects.filter(pk=book.book_detail.pk).update(publisher=publisher)
    return book

  def test_source(self):
    data = self.post('source', {'source-source': 'https://www.delpher.nl/nl/kranten/view?identifier=x'}).json()
    self.assertIn('<a href=https://www.delpher.nl', data['html'].replace('"', ''))
    self.assertIn('content-detail__field--wide', data['html'])   # the wide row, also after a save

  def test_book_publication_and_isbn(self):
    self.item = self.make_book()
    data = self.post('publication', {'publication-publisher': 'De Bezige Bij', 'publication-author': 'Anne-Lot Hoek'}).json()
    self.assertIn('De Bezige Bij', data['html'])
    self.post('isbn', {'isbn-isbn': '9789403152318'})
    detail = Content.objects.get(pk=self.item.pk).book_detail
    self.assertEqual((detail.publisher, detail.author, detail.isbn), ('De Bezige Bij', 'Anne-Lot Hoek', '9789403152318'))
    form = self.open_form('publication').json()['html'].replace('"', '')
    self.assertNotIn('publication_year', form)              # one date per book: the item's own (the date block)
    html = self.date(year='2021').json()['html']
    self.assertIn('Published', html)                        # a book's date is when it was published
    self.assertIn('2021', html)
    self.assertIn('data-cmnsd-suggest=/api/content/suggest/publisher/', form)
    self.assertIn('<datalist id=id_publication-publisher-suggestions>', form)

  def test_publisher_suggestions_most_used_first_and_only_visible(self):
    for name in ('De Bezige Bij', 'De Bezige Bij', 'Bezig Uitgevers'):
      self.make_book(name)
    other = self.user('other')
    self.make_book('Geheime Bezige Pers', owner=other, visibility='q')   # private to its owner
    client = self.client_for(self.editor, edit=False)
    values = client.get('/api/content/suggest/publisher/?q=bezig').json()['values']
    self.assertEqual(values, ['De Bezige Bij', 'Bezig Uitgevers'])
    self.assertEqual(Client().get('/api/content/suggest/publisher/?q=bezig').status_code, 403)
    self.assertEqual(client.get('/api/content/suggest/name/?q=x').status_code, 404)   # not a suggestion field


class ApiShapeOnContentTests(TestCase):
  """The one API response shape (cmnsd/views/api/response.py) on every
  endpoint, with a real item: ok, model, token where there's an object,
  messages; an error adds error + errors."""
  setUp = FieldBlockTests.setUp
  user = FieldBlockTests.user
  client_for = FieldBlockTests.client_for
  url = FieldBlockTests.url
  modified = FieldBlockTests.modified
  post = FieldBlockTests.post

  def test_success_shapes(self):
    client = self.client_for(self.editor)
    t = self.item.token
    calls = {
      'fields': client.get(f'/api/content/{t}/name/'),
      'list': client.get('/api/content/?q=Foto'),
      'form': client.get(f'/api/content/{t}/form/name/'),
      'suggest': client.get('/api/content/suggest/publisher/?q=x'),
      'action': client.post(f'/api/content/{t}/link/', '{"relation": "tags", "name": ""}', content_type='application/json'),
    }
    for name, response in calls.items():
      with self.subTest(endpoint=name):
        data = response.json()
        self.assertIn('ok', data)
        self.assertEqual(data['model'], 'content')
        self.assertIn('messages', data)
        if name in ('fields', 'form', 'action'):
          self.assertEqual(data['token'], t)
    self.assertFalse(calls['action'].json()['ok'])                     # no tag given: a validation error
    self.assertEqual(calls['action'].json()['errors'], {'validation': ["That wasn't found."]})

  def test_error_shapes(self):
    stale = self.post('description', {'description-description': 'x'}, modified='2000-01-01T00:00:00+00:00').json()
    self.assertEqual((stale['ok'], stale['errors'], stale['model'], stale['token']), (False, {'stale': True}, 'content', self.item.token))
    invalid = self.post('date', {'date-date_qualifier': 'exact', 'date-day': '31', 'date-month': '2', 'date-year': '1950'}).json()
    self.assertEqual(invalid['error'], 'Please correct the errors in the form.')
    self.assertIn('day', invalid['errors']['validation'])
    self.assertIn('html', invalid)                                     # the form with its errors, as before
