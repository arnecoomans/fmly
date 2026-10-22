from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase

from content.models import Content


class PhotoKindTests(TestCase):
  """The kinds of photo, each explained on its button (PhotoKindForm.choice_hints)."""

  def test_hints_and_candid(self):
    user = get_user_model().objects.create(username='redacteur')
    user.user_permissions.add(Permission.objects.get(codename='change_content'))
    user.save()
    client = Client()
    client.force_login(user)
    client.post('/ui/edit/', {'on': '1', 'next': '/'})
    item = Content.objects.create(name='Feest', kind='photo', user=user, status='p', visibility='c')
    html = client.get(item.get_absolute_url()).content.decode()
    self.assertIn('Posed, two or more people', html)
    item.refresh_from_db()
    response = client.post(f'/api/content/{item.token}/form/photo_kind/', {'_modified': item.date_modified.isoformat(), 'photo_kind-photo_kind': 'candid'})
    self.assertEqual(response.status_code, 200)
    self.assertEqual(Content.objects.get(pk=item.pk).photo_detail.photo_kind, 'candid')


class TranscribeLinkTests(TestCase):
  """The transcribe page is its own page: offered to whoever may
  transcribe, with or without edit mode; not to a reader."""

  def test_without_edit_mode(self):
    User = get_user_model()
    editor = User.objects.create(username='redacteur')
    editor.user_permissions.add(Permission.objects.get(codename='add_transcript'))
    editor.save()
    reader = User.objects.create(username='lezer')
    reader.save()
    item = Content.objects.create(name='Brief', kind='document', user=editor, status='p', visibility='c')
    url = f'/content/{item.token}/transcribe/'
    client = Client()
    client.force_login(editor)
    page = client.get(item.get_absolute_url()).content.decode()
    self.assertIn(url, page)
    self.assertIn('No transcript yet.', page)
    other = Client()
    other.force_login(reader)
    self.assertNotIn(url, other.get(item.get_absolute_url()).content.decode())

  def test_only_while_there_is_work(self):
    from content.models import Transcript
    editor = get_user_model().objects.create(username='redacteur')
    editor.user_permissions.add(Permission.objects.get(codename='change_transcript'))
    editor.save()
    item = Content.objects.create(name='Brief', kind='document', user=editor, status='p', visibility='c')
    done = Transcript.objects.create(content=item, kind='original', language='nl', method='manual', text='Lieve moeder')
    url = f'/content/{item.token}/transcribe/'
    client = Client()
    client.force_login(editor)
    self.assertNotIn(url, client.get(item.get_absolute_url()).content.decode())   # done: edit mode only
    done.incomplete = True
    done.save()
    self.assertIn(url, client.get(item.get_absolute_url()).content.decode())      # still work to do


class QuietTranscriptTests(TestCase):
  """On a photo a transcript is the exception: no section until there's
  one; in edit mode a quiet "+ transcript". A document keeps its section."""

  def test_photo(self):
    from content.models import Transcript
    editor = get_user_model().objects.create(username='stil')
    for codename in ('add_transcript', 'change_content'):
      editor.user_permissions.add(Permission.objects.get(codename=codename))
    editor.save()
    photo = Content.objects.create(name='Achterkant', kind='photo', user=editor, status='p', visibility='c')
    client = Client()
    client.force_login(editor)
    page = client.get(photo.get_absolute_url()).content.decode()
    self.assertNotIn('No transcript yet.', page)
    self.assertNotIn('content-detail__transcripts', page)
    client.post('/ui/edit/', {'on': '1', 'next': '/'})
    page = client.get(photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('content-detail__add-transcript', page)
    Transcript.objects.create(content=photo, kind='original', language='nl', method='manual', text='Krangan, Mei 1938')
    client.post('/ui/edit/', {'on': '0', 'next': '/'})
    self.assertIn('Krangan, Mei 1938', client.get(photo.get_absolute_url()).content.decode())   # there is one: shown
