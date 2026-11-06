import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from cmnsd.edit.mode import SESSION_KEY
from content.models import Content
from content.tests.test_upload import jpeg
from events.models import Event
from people.models import Person

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class UploadForEventTests(TestCase):
  """Adding documentation from an event's page: content_upload's `event`
  links the new draft - or an item that has the file already - as the
  event's proof, and nothing else: not its people, date or places."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = self.make_user('uploader', 'add_content', 'change_content', 'change_event')
    self.client = Client()
    self.client.force_login(self.user)
    self.bride = Person.objects.create(given_name='Marie', last_name='Bake', user=self.user, status='p', visibility='c')
    self.event = Event.objects.create(kind='marriage', year=1910, month=2, day=2, user=self.user, status='p')
    self.event.people.add(self.bride)

  def make_user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def upload(self, event=None, data=None, client=None):
    body = {'file': SimpleUploadedFile('IMG_1234.jpg', data or jpeg(), 'image/jpeg')}
    if event is not None:
      body['event'] = event
    return (client or self.client).post('/content/new/upload/', body)

  def test_new_draft_is_its_proof_only(self):
    self.assertEqual(self.upload(self.event.token).status_code, 200)
    item = Content.objects.get()
    self.assertEqual((item.status, list(item.events.all())), ('c', [self.event]))
    self.assertFalse(item.people.exists())                                  # the event brings it to their pages
    self.assertIsNone(item.year)                                            # an announcement isn't the wedding's date

  def test_unknown_event_stores_nothing(self):
    self.assertEqual(self.upload('nosuchtoken').status_code, 400)
    self.assertFalse(Content.objects.exists())

  def test_an_event_you_may_not_change_stores_nothing(self):
    other = self.make_user('other', 'add_content')
    client = Client()
    client.force_login(other)
    self.assertEqual(self.upload(self.event.token, client=client).status_code, 403)
    self.assertFalse(Content.objects.exists())

  def test_duplicate_is_linked_as_proof(self):
    self.upload(data=jpeg('red'))
    response = self.upload(self.event.token, data=jpeg('red'))
    self.assertEqual(Content.objects.count(), 1)
    self.assertTrue(response.json()['duplicate']['linked'])
    self.assertEqual(list(Content.objects.get().events.all()), [self.event])

  def test_dropzone_in_edit_mode(self):
    url = self.event.get_absolute_url()
    self.assertNotIn('data-upload-param', self.client.get(url).content.decode())
    session = self.client.session
    session[SESSION_KEY] = True
    session.save()
    page = self.client.get(url).content.decode().replace('"', '')
    self.assertRegex(page, rf'<input data-upload-param name=event type=hidden value={self.event.token}>')
    self.assertIn('Add documentation for this event', page)
