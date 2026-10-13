import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings

from cmnsd.edit.mode import SESSION_KEY
from content.models import Content
from content.tests.test_upload import jpeg
from people.models import Person

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA)
class UploadForPersonTests(TestCase):
  """Adding content from a person's page (issue #456): content_upload's
  `person` links the new draft - or an item that has the file already -
  to that person; the dropzone on the person page."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = self.make_user('uploader', 'add_content', 'change_content', 'change_person')
    self.client = Client()
    self.client.force_login(self.user)
    self.person = Person.objects.create(given_name='Jan', last_name='Bake', user=self.user, status='p', visibility='c')

  def make_user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def upload(self, person=None, data=None, client=None, name='IMG_1234.jpg'):
    body = {'file': SimpleUploadedFile(name, data or jpeg(), 'image/jpeg')}
    if person is not None:
      body['person'] = person
    return (client or self.client).post('/content/new/upload/', body)

  def test_new_draft_is_linked(self):
    response = self.upload(self.person.token)
    self.assertEqual(response.status_code, 200)
    item = Content.objects.get()
    self.assertEqual((item.status, list(item.people.all())), ('c', [self.person]))

  def test_without_person_nothing_is_linked(self):
    self.upload()
    self.assertFalse(Content.objects.get().people.exists())

  def test_unknown_or_hidden_person_stores_nothing(self):
    self.assertEqual(self.upload('nosuchtoken').status_code, 400)
    hidden = Person.objects.create(given_name='Geheim', user=self.make_user('owner'), status='p', visibility='q')
    self.assertEqual(self.upload(hidden.token).status_code, 400)
    self.assertFalse(Content.objects.exists())

  def test_duplicate_gets_the_person_linked(self):
    self.upload(data=jpeg('red'))
    response = self.upload(self.person.token, data=jpeg('red'))
    self.assertEqual(Content.objects.count(), 1)
    self.assertTrue(response.json()['duplicate']['linked'])
    self.assertEqual(list(Content.objects.get().people.all()), [self.person])
    # Again: still linked once, still answered as linked.
    self.assertTrue(self.upload(self.person.token, data=jpeg('red')).json()['duplicate']['linked'])
    self.assertEqual(Content.objects.get().people.count(), 1)

  def test_duplicate_you_may_not_change_is_only_reported(self):
    other = self.make_user('other', 'add_content')   # may add, not change others' items
    other_client = Client()
    other_client.force_login(other)
    self.upload(data=jpeg('blue'))
    Content.objects.update(status='p')               # published: the other may see it
    response = self.upload(self.person.token, data=jpeg('blue'), client=other_client)
    self.assertFalse(response.json()['duplicate']['linked'])
    self.assertFalse(Content.objects.get().people.exists())

  def test_dropzone_only_in_edit_mode(self):
    url = self.person.page_url()
    self.assertNotIn('data-upload-param', self.client.get(url).content.decode())
    session = self.client.session
    session[SESSION_KEY] = True
    session.save()
    page = self.client.get(url).content.decode().replace('"', '')
    # Also without content yet (the section's empty_body). The minifier reorders attributes.
    self.assertRegex(page, rf'<input data-upload-param name=person type=hidden value={self.person.token}>')

  def test_no_dropzone_without_add_permission(self):
    reader = self.make_user('reader', 'change_person')
    client = Client()
    client.force_login(reader)
    session = client.session
    session[SESSION_KEY] = True
    session.save()
    self.assertNotIn('data-upload-param', client.get(self.person.page_url()).content.decode())
