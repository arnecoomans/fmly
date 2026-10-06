from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content, Transcript


class TranscriptEditingTests(TestCase):
  """Transcripts as child records of an item (cmnsd object_children,
  Content.api_editable_children): add, edit, remove - with the transcript
  permissions, separate from editing the item."""

  def setUp(self):
    self.transcriber = self.user('transcriber', 'add_transcript', 'change_transcript', 'delete_transcript')
    self.editor = self.user('editor', 'change_content')               # may edit the item, not its transcripts
    self.item = Content.objects.create(name='Brief', kind='document', user=self.editor, status='p', visibility='c')
    self.original = Transcript.objects.create(content=self.item, kind='original', language='nl', text='Lieve moeder,')

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

  def base(self):
    return f'/api/content/{self.item.token}/children/transcripts/'

  def add(self, user=None, **fields):
    data = {'transcripts-kind': 'translation', 'transcripts-language': 'en', 'transcripts-method': 'manual',
            'transcripts-text': 'Dear mother,'}
    data.update({f'transcripts-{key}': value for key, value in fields.items()})
    return self.client_for(user or self.transcriber).post(self.base(), data)

  def test_add_returns_the_child_and_a_new_add(self):
    response = self.add()
    self.assertEqual(response.status_code, 200)
    data = response.json()
    html = data['html'].replace('"', '')
    self.assertIn('Dear mother,', html)
    self.assertIn('id=edit-child-content-transcripts-new', html)          # a fresh "+ add" after the new one
    self.assertIn('Transcript added.', [m['text'] for m in data['messages']])
    self.assertEqual(self.item.transcripts.count(), 2)
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.item.pk), change_message__startswith='Added transcript').exists())

  def test_rules_are_form_errors_not_crashes(self):
    same_language = self.add(language='nl').json()
    self.assertIn('already has a transcript in that language', same_language['html'])
    second_original = self.add(kind='original', language='de').json()
    self.assertIn('already has an original', second_original['html'])
    empty = self.add(text='   ')
    self.assertEqual(empty.status_code, 400)
    self.assertEqual(self.item.transcripts.count(), 1)

  def edit_url(self, transcript):
    return f'{self.base()}{transcript.pk}/'

  def test_edit_and_stale(self):
    client = self.client_for(self.transcriber)
    form = client.get(self.edit_url(self.original)).json()['html']
    self.assertIn('Lieve moeder,', form)
    modified = Transcript.objects.get(pk=self.original.pk).date_modified.isoformat()
    data = {'_modified': modified, 'transcripts-kind': 'original', 'transcripts-language': 'nl',
            'transcripts-method': 'manual', 'transcripts-text': 'Lieve moeder, hier is alles goed.'}
    self.assertEqual(client.post(self.edit_url(self.original), data).status_code, 200)
    self.assertEqual(Transcript.objects.get(pk=self.original.pk).text, 'Lieve moeder, hier is alles goed.')
    self.assertEqual(client.post(self.edit_url(self.original), data).status_code, 409)   # the old version again

  def test_remove(self):
    response = self.client_for(self.transcriber).post(f'{self.edit_url(self.original)}delete/')
    self.assertTrue(response.json()['removed'])
    self.assertFalse(Transcript.objects.filter(pk=self.original.pk).exists())

  def test_permissions_are_the_transcript_ones(self):
    self.assertEqual(self.add(user=self.editor).status_code, 403)          # change_content isn't enough
    self.assertEqual(self.client_for(self.editor).post(f'{self.edit_url(self.original)}delete/').status_code, 403)
    self.assertEqual(Client().post(self.base(), {}).status_code, 404)      # signed out: the item isn't visible

  def test_another_items_transcript_is_not_found(self):
    other = Content.objects.create(name='Ander', kind='document', user=self.editor, status='p', visibility='c')
    foreign = Transcript.objects.create(content=other, kind='original', language='nl', text='x')
    self.assertEqual(self.client_for(self.transcriber).get(self.edit_url(foreign)).status_code, 404)

  def test_page_in_edit_mode(self):
    html = self.client_for(self.transcriber).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'id=edit-child-content-transcripts-{self.original.pk}', html)
    self.assertIn('Add a transcript or translation', html)
    editor_html = self.client_for(self.editor).get(self.item.get_absolute_url()).content.decode()
    self.assertNotIn('edit-child-content-transcripts', editor_html)        # no transcript permissions
    self.assertIn('Lieve moeder,', editor_html)                            # still shown, as normal


class TranscribePageTests(TestCase):
  """content/<token>/transcribe/ (TranscribeView): the image beside the
  transcript, which saves itself through the child-record endpoints."""
  setUp = TranscriptEditingTests.setUp
  user = TranscriptEditingTests.user
  client_for = TranscriptEditingTests.client_for
  base = TranscriptEditingTests.base

  def url(self, item=None, query=''):
    return f'/content/{(item or self.item).token}/transcribe/{query}'

  def page(self, query='', user=None, item=None):
    return self.client_for(user or self.transcriber, edit=False).get(self.url(item, query))

  def html(self, *args, **kwargs):
    return self.page(*args, **kwargs).content.decode().replace('"', '')

  def test_opens_the_original_by_default(self):
    html = self.html()
    self.assertIn('Lieve moeder,</textarea>', html)
    self.assertIn(f'action=/api/content/{self.item.token}/children/transcripts/{self.original.pk}/', html)
    self.assertIn('data-cmnsd-autosave', html)
    self.assertNotIn('app-topbar', html)                                   # no site header: full focus

  def test_new_is_a_translation_posting_to_the_add_address(self):
    html = self.html('?transcript=new')
    self.assertIn(f'action=/api/content/{self.item.token}/children/transcripts/', html)
    self.assertIn('data-cmnsd-autosave=new', html)
    self.assertRegex(html, r'<option selected value=translation>')         # an original exists already

  def test_access(self):
    self.assertEqual(self.page(user=self.editor).status_code, 403)         # no transcript permissions
    self.assertEqual(Client().get(self.url()).status_code, 302)            # signed out: to sign in
    self.assertEqual(self.page('?transcript=999999').status_code, 404)

  def test_pages_of_a_whole(self):
    part = Content.objects.create(name='Achterkant', kind='document', user=self.editor, status='p', visibility='c')
    self.item.make_parts_of([part])
    html = self.html(item=part)
    self.assertIn('page 2 of 2', html)
    self.assertIn(f'href=/content/{self.item.token}/transcribe/ rel=prev', html)

  def test_create_tells_where_the_new_transcript_lives(self):
    response = self.client_for(self.transcriber).post(self.base(), {
      'transcripts-kind': 'translation', 'transcripts-language': 'en', 'transcripts-method': 'manual',
      'transcripts-text': 'Dear mother,'})
    data = response.json()
    created = Transcript.objects.get(content=self.item, language='en')
    self.assertEqual(data['child']['edit'], f'{self.base()}{created.pk}/')
    self.assertEqual(data['modified'], created.date_modified.isoformat())

  def test_transcribe_is_a_reserved_slug(self):
    named = Content.objects.create(name='Transcribe', kind='photo', user=self.editor, status='p', visibility='c')
    self.assertNotEqual(named.slug, 'transcribe')


class TranscribeFlowTests(TestCase):
  """Editing goes through the transcribe page; incomplete; Close; the
  original's text beside a translation."""
  setUp = TranscriptEditingTests.setUp
  user = TranscriptEditingTests.user
  client_for = TranscriptEditingTests.client_for
  base = TranscriptEditingTests.base
  url = TranscribePageTests.url
  page = TranscribePageTests.page
  html = TranscribePageTests.html

  def test_item_page_pencil_and_add_go_to_the_transcribe_page(self):
    html = self.client_for(self.transcriber).get(self.item.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'href=/content/{self.item.token}/transcribe/?transcript={self.original.pk}', html)
    self.assertIn(f'href=/content/{self.item.token}/transcribe/?transcript=new', html)
    self.assertNotIn('data-cmnsd-edit-url=/api/content/', html.split('content-detail__transcripts')[1].split('</section>')[0])

  def test_incomplete_is_saved_and_shown(self):
    client = self.client_for(self.transcriber)
    modified = Transcript.objects.get(pk=self.original.pk).date_modified.isoformat()
    client.post(f'{self.base()}{self.original.pk}/', {
      '_modified': modified, 'transcripts-kind': 'original', 'transcripts-language': 'nl',
      'transcripts-method': 'manual', 'transcripts-incomplete': 'on', 'transcripts-text': 'Lieve moeder, ...'})
    self.assertTrue(Transcript.objects.get(pk=self.original.pk).incomplete)
    self.assertIn('incomplete', self.client_for(self.editor, edit=False).get(self.item.get_absolute_url()).content.decode())

  def test_close_button_tied_to_the_form(self):
    html = self.html()
    self.assertIn('data-autosave-close=transcribe-form', html)
    self.assertIn('id=transcribe-form', html)

  def test_translation_opens_beside_the_original(self):
    translation = Transcript.objects.create(content=self.item, kind='translation', language='en', text='Dear mother,')
    html = self.html(f'?transcript={translation.pk}')
    self.assertIn('class=transcribe__original-text>Lieve moeder,', html)    # the original on the left
    self.assertIn('left=original', html)                                    # the switch (no image to switch to: this item has no file)
    image_side = self.html(f'?transcript={translation.pk}&left=image')
    self.assertNotIn('transcribe__original-text', image_side)
    self.assertNotIn('transcribe__original-text', self.html())              # the original itself: no switch
