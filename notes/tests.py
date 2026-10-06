import json
import tempfile
from pathlib import Path

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.management import call_command
from django.test import Client, TestCase

from content.models import Content
from people.models import Person

from .models import Note


class NoteTestCase(TestCase):
  def setUp(self):
    self.author = self.user('author', 'add_note', 'change_note')
    self.other = self.user('other')
    self.shown = Person.objects.create(given_name='Pieter', user=self.author, status='p', visibility='p')
    self.hidden = Person.objects.create(given_name='Verborgen', user=self.other, status='p', visibility='q')

  def user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def client_for(self, user, edit=False):
    client = Client()
    client.force_login(user)
    if edit:
      client.post('/ui/edit/', {'on': '1', 'next': '/'})
    return client

  def note(self, **fields):
    return Note.objects.create(**{'user': self.author, **fields})

  def html(self, url, client):
    return client.get(url).content.decode().replace('"', '')


class NoteModelTests(NoteTestCase):
  def test_a_new_note_is_a_private_draft(self):
    note = self.note()
    self.assertEqual((note.status, note.visibility, note.kind), ('c', 'q', 'scratch'))

  def test_name_falls_back_to_the_first_line(self):
    self.assertEqual(str(self.note(title='Medan')), 'Medan')
    self.assertEqual(str(self.note(body='## Wie ging wanneer\nnaar Indië')), 'Wie ging wanneer')
    self.assertEqual(str(self.note()), 'untitled note')

  def test_open_work_first(self):
    context = self.note(kind='context', title='a')
    todo = self.note(kind='todo', title='b')
    question = self.note(kind='question', title='c')
    self.assertEqual(list(Note.objects.in_order()), [todo, question, context])


class NoteVisibilityTests(NoteTestCase):
  """A draft or private note only for its author; the rest by visibility."""

  def setUp(self):
    super().setUp()
    self.draft = self.note(title='Mijn kladje')
    self.shared = self.note(title='Gedeeld', status='p', visibility='c')

  def test_others_see_only_published_shared_notes(self):
    other = self.client_for(self.other)
    html = self.html('/notes/', other)
    self.assertIn('Gedeeld', html)
    self.assertNotIn('Mijn kladje', html)
    self.assertEqual(other.get(self.draft.get_absolute_url()).status_code, 404)
    self.assertEqual(Client().get(self.shared.get_absolute_url()).status_code, 404)    # signed out: community isn't public

  def test_the_author_sees_their_draft(self):
    html = self.html('/notes/', self.client_for(self.author))
    self.assertIn('Mijn kladje', html)

  def test_api_list_is_visibility_filtered_and_no_page(self):
    data = self.client_for(self.other).get('/api/note/').json()
    self.assertEqual([row['token'] for row in data['results']], [self.shared.token])
    self.assertNotIn('html', data)                                         # no page template under the list's name

  def test_hidden_links_stay_unseen(self):
    self.shared.people.add(self.shown, self.hidden)
    html = self.html(self.shared.get_absolute_url(), self.client_for(self.author))
    self.assertIn('Pieter', html)
    self.assertNotIn('Verborgen', html)


class NoteCreateTests(NoteTestCase):
  """POST notes/new/ - a draft, linked to the page it was started from."""

  def test_starts_linked_to_the_page_and_in_edit_mode(self):
    client = self.client_for(self.author)
    response = client.post('/notes/new/', {'on': f'person:{self.shown.token}'})
    note = Note.objects.get()
    self.assertRedirects(response, f'{note.get_absolute_url()}?open=title,body')
    self.assertEqual(list(note.people.all()), [self.shown])
    self.assertEqual(note.user, self.author)
    self.assertTrue(LogEntry.objects.filter(object_id=str(note.pk), change_message='Created on the site').exists())
    self.assertIn(f'/api/note/{note.token}/form/body/', self.html(note.get_absolute_url(), client))   # edit mode on

  def test_never_linked_to_what_the_author_cant_see(self):
    self.client_for(self.author).post('/notes/new/', {'on': f'person:{self.hidden.token}'})
    self.assertFalse(Note.objects.get().people.exists())

  def test_needs_add_note(self):
    self.assertEqual(self.client_for(self.other).post('/notes/new/').status_code, 403)
    self.assertFalse(Note.objects.exists())

  def test_notes_section_on_a_person_page(self):
    self.note(title='Over Pieter', status='p', visibility='c').people.add(self.shown)
    self.note(title='Privé over Pieter', user=self.other).people.add(self.shown)
    html = self.html(self.shown.get_absolute_url(), self.client_for(self.author))
    self.assertIn('Over Pieter', html)
    self.assertNotIn('Privé over Pieter', html)                           # someone else's draft
    self.assertIn(f'value=person:{self.shown.token}', html)               # + New note starts linked here


class NoteEditTests(NoteTestCase):
  """Edit mode: blocks (Note.api_edit_forms) and links (EditableRelationsMixin)."""

  def setUp(self):
    super().setUp()
    self.question = self.note(title='Wie ging naar Indië?', kind='question')
    self.client = self.client_for(self.author, edit=True)

  def save(self, block, **fields):
    self.question.refresh_from_db()
    data = {'_modified': self.question.date_modified.isoformat(), **{f'{block}-{k}': v for k, v in fields.items()}}
    return self.client.post(f'/api/note/{self.question.token}/form/{block}/', data)

  def link(self, relation, **data):
    return self.client.post(f'/api/note/{self.question.token}/link/', json.dumps({'relation': relation, **data}), content_type='application/json')

  def test_a_question_becomes_a_conclusion(self):
    self.assertEqual(self.save('kind', kind='conclusion').status_code, 200)
    self.assertEqual(Note.objects.get(pk=self.question.pk).kind, 'conclusion')
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.question.pk), change_message='Changed kind (on the page)').exists())

  def test_publish(self):
    self.assertEqual(self.save('status', status='p').status_code, 200)
    self.assertEqual(Note.objects.get(pk=self.question.pk).status, 'p')

  def test_body_and_date(self):
    self.save('body', body='In **1921** naar Batavia.')
    response = self.save('date', date_qualifier='circa', day='', month='', year='1921')
    self.assertEqual(response.status_code, 200, response.json().get('errors'))
    html = self.html(self.question.get_absolute_url(), self.client)
    self.assertIn('<strong>1921</strong>', html)
    self.assertEqual(Note.objects.get(pk=self.question.pk).year, 1921)

  def test_link_people_content_and_a_new_tag(self):
    item = Content.objects.create(name='Paspoort', kind='document', user=self.author, status='p', visibility='c')
    self.assertEqual(self.link('people', token=self.shown.token).status_code, 200)
    self.assertEqual(self.link('content', token=item.token).status_code, 200)
    self.assertEqual(self.link('people', token=self.hidden.token).status_code, 400)   # not visible: not found
    self.author.user_permissions.add(Permission.objects.get(codename='add_tag'))
    self.author = get_user_model().objects.get(pk=self.author.pk)   # fresh permission cache
    self.client = self.client_for(self.author, edit=True)
    self.assertEqual(self.link('tags', name='Emigratie').status_code, 200)
    self.assertEqual(list(self.question.tags.values_list('name', flat=True)), ['Emigratie'])
    self.assertEqual(list(item.notes.all()), [self.question])

  def test_links_to_another_note_one_way(self):
    context = self.note(title='De Indische tijd', kind='context', status='p', visibility='c')
    self.assertEqual(self.link('related_notes', token=context.token).status_code, 200)
    self.assertEqual(list(self.question.related_notes.all()), [context])
    self.assertFalse(context.related_notes.exists())                      # one way...
    html = self.html(context.get_absolute_url(), self.client)
    self.assertIn('Linked from', html)                                    # ...but shown on both
    self.assertIn('Wie ging naar Indië?', html)

  def test_needs_change_note(self):
    reader = self.client_for(self.user('reader', 'change_content'), edit=True)
    self.question.visibility = 'c'
    self.question.status = 'p'
    self.question.save()
    self.assertEqual(reader.post(f'/api/note/{self.question.token}/form/kind/', {}).status_code, 403)


class ImportNotesTests(TestCase):
  """legacy_import import_notes: matched by token, links rewritten, kinds kept."""

  def test_import(self):
    user = get_user_model().objects.create(username='arne')
    user.save()
    person = Person.objects.create(pk=59, given_name='Willem', user=user, status='p', visibility='p')
    Note.objects.create(pk=1, user=user, title='Al op de site gemaakt')   # takes legacy pk 1
    rows = [{'model': 'archive.note', 'pk': 1, 'fields': {
      'token': 'b0d7f5ce96e84621a88b', 'status': 'p', 'user': user.pk, 'title': 'Welkom',
      'content': 'Zie [Willem](/person/59/willem-bake/).', 'people': [59], 'tags': [],
      'date_created': '2022-01-07T21:14:39Z', 'date_modified': '2022-01-25T13:38:25Z',
    }}]
    with tempfile.TemporaryDirectory() as folder:
      path = Path(folder) / 'archive_note.json'
      path.write_text(json.dumps(rows))
      call_command('import_notes', path=str(path), stdout=open('/dev/null', 'w'))
      imported = Note.objects.get(token='b0d7f5ce96e84621a88b')
      imported.kind = 'conclusion'
      imported.save()
      call_command('import_notes', path=str(path), stdout=open('/dev/null', 'w'))
    self.assertEqual(Note.objects.get(pk=1).title, 'Al op de site gemaakt')   # not overwritten
    imported.refresh_from_db()
    self.assertEqual(Note.objects.filter(token='b0d7f5ce96e84621a88b').count(), 1)
    self.assertIn(f']({person.get_absolute_url()})', imported.body)
    self.assertEqual((imported.status, imported.visibility, imported.kind), ('p', 'c', 'conclusion'))
    self.assertEqual(list(imported.people.all()), [person])
    self.assertEqual(imported.date_created.year, 2022)
