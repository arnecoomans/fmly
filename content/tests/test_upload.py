import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content
from content.uploads import guess_kind

MEDIA = tempfile.mkdtemp()


def jpeg(color='white', size=(60, 40)):
  buffer = io.BytesIO()
  Image.new('RGB', size, color).save(buffer, 'JPEG')
  return buffer.getvalue()


@override_settings(MEDIA_ROOT=MEDIA)
class UploadTests(TestCase):
  """content/new/ - each file a draft in the uploader's inbox; a file
  that's in the archive already is pointed out (checksum)."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.user = self.make_user('uploader', 'add_content', 'change_content')
    self.client = Client()
    self.client.force_login(self.user)

  def make_user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def upload(self, name='IMG_1234.jpg', data=None, client=None):
    return (client or self.client).post('/content/new/upload/', {'file': SimpleUploadedFile(name, data or jpeg(), 'image/jpeg')})

  def test_a_file_becomes_a_draft(self):
    response = self.upload('Paspoort Johan.jpg')
    self.assertEqual(response.status_code, 200)
    item = Content.objects.get()
    self.assertEqual((item.status, item.visibility, item.kind, item.user), ('c', 'c', 'photo', self.user))
    self.assertEqual(len(item.checksum), 64)
    self.assertEqual(item.name, 'Paspoort Johan')                           # a file name that says something
    self.upload('IMG_1234.jpg', jpeg('green'))
    self.assertEqual(Content.objects.get(original_filename='IMG_1234.jpg').name, '')   # one that doesn't
    created = response.json()['created']
    self.assertEqual(created['url'], item.get_absolute_url())
    self.assertTrue(created['thumb'].endswith('/thumb/avatar/'))
    self.assertEqual(self.client_for_other().get(item.get_absolute_url()).status_code, 404)   # a draft: only theirs

  def client_for_other(self):
    other = Client()
    other.force_login(self.make_user('other'))
    return other

  def test_the_same_file_twice(self):
    self.upload('scan.jpg', jpeg('red'))
    response = self.upload('scan-kopie.jpg', jpeg('red'))
    self.assertEqual(Content.objects.count(), 1)
    duplicate = response.json()['duplicate']
    self.assertEqual(duplicate['url'], Content.objects.get().get_absolute_url())
    # Someone else's draft: "already in the archive", but no link to it.
    other = self.make_user('second', 'add_content')
    client = Client()
    client.force_login(other)
    self.assertEqual(self.upload('scan.jpg', jpeg('red'), client).json()['duplicate']['url'], '')

  def test_needs_add_content(self):
    client = Client()
    client.force_login(self.make_user('reader'))
    self.assertEqual(self.upload(client=client).status_code, 403)
    self.assertEqual(client.get('/content/new/').status_code, 403)

  def test_kind_by_file(self):
    self.assertEqual(guess_kind('brief.pdf'), 'document')
    self.assertEqual(guess_kind('interview.mp3'), 'recording')
    self.assertEqual(guess_kind('foto.jpg'), 'photo')
    self.assertEqual(guess_kind('data.xyz'), 'unknown')


@override_settings(MEDIA_ROOT=MEDIA)
class InboxTests(UploadTests):
  """content/inbox/ - your drafts; make several one item; next in inbox."""

  def test_inbox_lists_your_drafts_only(self):
    self.upload('a.jpg', jpeg('red'))
    self.upload('b.jpg', jpeg('blue'))
    Content.objects.create(name='Gepubliceerd', kind='photo', user=self.user, status='p', visibility='c')
    html = self.client.get('/content/inbox/').content.decode()
    self.assertIn('2 drafts', html)
    self.assertNotIn('Gepubliceerd', html)
    self.assertIn('0 drafts', self.client_for_other_with_perm().get('/content/inbox/').content.decode())

  def client_for_other_with_perm(self):
    client = Client()
    client.force_login(self.make_user('third', 'add_content'))
    return client

  def test_make_one_item(self):
    for color in ('red', 'green', 'blue'):
      self.upload(f'pagina-{color}.jpg', jpeg(color))
    red, green, blue = Content.objects.order_by('pk')
    self.client.post('/content/inbox/group/', {'tokens': [red.token, green.token, blue.token]})
    # The inbox's order - by name: blue, green, red - whatever order they're posted in.
    self.assertEqual([p.pk for p in blue.parts.order_by('position')], [green.pk, red.pk])
    green.refresh_from_db()
    self.assertEqual((green.parent, green.position), (blue, 1))

  def test_a_batch_in_name_order(self):
    # The browser sent page 10 first, then 2, then 1: the inbox reads 1, 2, 10.
    for page, color in ((10, 'red'), (2, 'green'), (1, 'blue')):
      self.upload(f'Scan page {page}.jpg', jpeg(color))
    html = self.client.get('/content/inbox/').content.decode()
    self.assertLess(html.index('Scan page 1'), html.index('Scan page 2'))
    self.assertLess(html.index('Scan page 2'), html.index('Scan page 10'))
    one, two, ten = (Content.objects.get(name=f'Scan page {n}') for n in (1, 2, 10))
    self.client.post('/content/inbox/group/', {'tokens': [one.token, two.token, ten.token]})
    self.assertEqual([p.pk for p in one.parts.order_by('position')], [two.pk, ten.pk])   # the whole: page 1

  def test_next_in_inbox(self):
    self.upload('een.jpg', jpeg('red'))
    self.upload('twee.jpg', jpeg('blue'))
    first, second = Content.objects.order_by('pk')
    html = self.client.get(first.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('content-detail__inbox', html)
    self.assertIn(f'href={second.get_absolute_url()}', html)


class OthersDraftsTests(TestCase):
  """Staff see other people's drafts on their inbox page (in case they
  forget them) - not a private one; an editor only their own."""

  def test_staff_see_others_drafts(self):
    User = get_user_model()
    staff = User.objects.create(username='beheer', is_staff=True)
    staff.user_permissions.add(Permission.objects.get(codename='add_content'))
    staff.save()
    uploader = User.objects.create(username='oom')
    uploader.user_permissions.add(Permission.objects.get(codename='add_content'))
    uploader.save()
    Content.objects.create(name='Vergeten scan', kind='photo', user=uploader, status='c', visibility='c')
    Content.objects.create(name='Geheim', kind='photo', user=uploader, status='c', visibility='q')
    client = Client()
    client.force_login(staff)
    html = client.get('/content/inbox/').content.decode()
    self.assertIn('Vergeten scan', html)
    self.assertNotIn('Geheim', html)
    self.assertIn('1 draft by others', client.get('/').content.decode())     # the dashboard's inbox block
    own = Client()
    own.force_login(uploader)
    self.assertNotIn("other people", own.get('/content/inbox/').content.decode())
