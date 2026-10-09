import io
import shutil
import tempfile
from pathlib import Path

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class HousekeepingTests(TestCase):
  """dashboard/housekeeping/ (dashboard/housekeeping.py): staff who may
  delete content; purging deleted items and removing files without a
  record, each only after a confirmation page."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    User = get_user_model()
    self.staff = User.objects.create(username='beheer', is_staff=True)
    self.staff.user_permissions.add(Permission.objects.get(codename='delete_content'))
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)

  def item(self, name, status='p', parent=None):
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'white').save(buffer, 'JPEG')
    item = Content.objects.create(name=name, kind='photo', user=self.staff, status=status, visibility='c', parent=parent)
    item.file.save(f'{name}.jpg', ContentFile(buffer.getvalue()))
    return item

  def test_staff_who_may_delete_only(self):
    editor = get_user_model().objects.create(username='redacteur')
    editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    editor.save()
    client = Client()
    client.force_login(editor)
    self.assertEqual(client.get('/dashboard/housekeeping/').status_code, 404)
    self.assertNotIn('/dashboard/housekeeping/', client.get('/people/').content.decode())   # nor in their menu
    self.assertEqual(self.client.get('/dashboard/housekeeping/').status_code, 200)
    self.assertIn('/dashboard/housekeeping/', self.client.get('/people/').content.decode())  # in the user menu

  def test_purge_after_confirmation(self):
    gone = self.item('weg', status='x')
    path = Path(gone.file.path)
    kept = self.item('blijft')
    first = self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [gone.token, kept.token]})
    self.assertContains(first, 'weg')
    self.assertTrue(Content.objects.filter(pk=gone.pk).exists())          # not yet: only the list
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [gone.token, kept.token], 'confirm': '1'})
    self.assertFalse(Content.objects.filter(pk=gone.pk).exists())
    self.assertFalse(path.exists())
    self.assertTrue(Content.objects.filter(pk=kept.pk).exists())           # not deleted: never purged
    self.assertTrue(LogEntry.objects.filter(object_id=str(gone.pk), action_flag=3).exists())

  def test_an_item_with_live_parts_stays(self):
    whole = self.item('boek', status='x')
    self.item('pagina', parent=whole)
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [whole.token], 'confirm': '1'})
    self.assertTrue(Content.objects.filter(pk=whole.pk).exists())

  def test_files_without_a_record(self):
    item = self.item('bekend')
    orphan = Path(MEDIA) / 'content' / '2020' / 'los.jpg'
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_bytes(b'x')
    page = self.client.get('/dashboard/housekeeping/').content.decode()
    self.assertIn('content/2020/los.jpg', page)
    self.assertNotIn(f'value="{item.file.name}"', page)
    self.client.post('/dashboard/housekeeping/', {'action': 'files', 'file': ['content/2020/los.jpg', item.file.name, '../db.sqlite3'], 'confirm': '1'})
    self.assertFalse(orphan.exists())
    self.assertTrue(Path(item.file.path).exists())                         # has a record: never deleted

  def test_a_deleted_duplicate_is_purged_from_its_pair(self):
    kept = self.item('origineel')
    copy = self.item('kopie', status='x')
    Content.objects.filter(pk__in=[kept.pk, copy.pk]).update(checksum='a' * 64)
    page = self.client.get('/dashboard/housekeeping/').content.decode().replace('"', '')
    self.assertLess(page.index('same file twice'.capitalize()), page.index('Deleted items'))   # first on the page
    self.assertIn(f'value={copy.token}', page)
    self.assertNotIn(f'value={kept.token}', page)                         # not deleted: no checkbox
    path = Path(copy.file.path)
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [copy.token], 'confirm': '1'})
    self.assertFalse(Content.objects.filter(pk=copy.pk).exists())
    self.assertFalse(path.exists())
    self.assertTrue(Path(kept.file.path).exists())

  def test_a_file_shared_with_another_item_is_kept(self):
    kept = self.item('origineel')
    copy = Content.objects.create(name='zelfde', kind='photo', user=self.staff, status='x', visibility='c')
    Content.objects.filter(pk=copy.pk).update(file=kept.file.name)           # the very same stored file
    self.client.post('/dashboard/housekeeping/', {'action': 'purge', 'item': [copy.token], 'confirm': '1'})
    self.assertFalse(Content.objects.filter(pk=copy.pk).exists())
    self.assertTrue(Path(kept.file.path).exists())

  def test_staff_open_a_deleted_item_marked_deleted(self):
    gone = self.item('verwijderd', status='x')
    page = self.client.get(gone.get_absolute_url())
    self.assertContains(page, 'content-detail__deleted')
    self.assertEqual(self.client.get(f'/content/{gone.token}/thumb/card/').status_code, 200)
    self.assertNotContains(self.client.get('/content/'), 'verwijderd')     # never in a list
    member = get_user_model().objects.create(username='lid')
    member.save()
    client = Client()
    client.force_login(member)
    self.assertEqual(client.get(gone.get_absolute_url()).status_code, 404)
    self.assertEqual(client.get(f'/content/{gone.token}/thumb/card/').status_code, 404)

  def test_comments_on_a_deleted_item_show_on_its_page_only(self):
    from core.models import Comment
    gone = self.item('verwijderd', status='x')
    Comment.objects.create(target=gone, user=self.staff, content='Een dubbele', status='p')
    self.assertContains(self.client.get(gone.get_absolute_url()), 'Een dubbele')
    self.assertNotContains(self.client.get('/comments/'), 'Een dubbele')    # not in the feed

  def test_a_deleted_items_sections_are_never_folded(self):
    whole = self.item('verwijderd boek', status='x')
    self.item('pagina', parent=whole)
    html = self.client.get(whole.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('data-cmnsd-section=content.parts', html)               # plain, not a fold
    self.assertIn('pagina', html)


class UnusedTagsAndPlacesTests(TestCase):
  """Housekeeping: unused tags and places (issue #460) - listed by eye,
  deleted after a confirmation, by staff who may delete them."""

  def setUp(self):
    from core.models import Tag
    from places.models import Place
    User = get_user_model()
    self.staff = User.objects.create(username='beheer', is_staff=True)
    for codename in ('delete_content', 'delete_tag', 'delete_place'):
      self.staff.user_permissions.add(Permission.objects.get(codename=codename))
    self.staff.save()
    self.client = Client()
    self.client.force_login(self.staff)
    make_tag = lambda name, **f: Tag.objects.create(name=name, user=self.staff, status='p', visibility='c', **f)
    self.old_category, self.used = make_tag('Advertisement'), make_tag('Krangan 81')
    self.collection = make_tag('Collection')
    make_tag('Boeken', parent=self.collection)                                   # Collection has a child: used
    from core.tags import LOOSE_END_SLUG
    make_tag('Loose end', slug=LOOSE_END_SLUG)                                    # never offered
    Content.objects.create(name='Foto', kind='photo', user=self.staff, status='p', visibility='c').tags.add(self.used)
    make_place = lambda name, **f: Place.objects.create(name=name, user=self.staff, **f)
    self.lone, self.batavia, self.djakarta = make_place('Nieuw Guinea'), make_place('Batavia'), make_place('Djakarta')
    self.batavia.alternatives.add(self.djakarta)                                  # another era's name: used

  def test_listed(self):
    from dashboard import housekeeping
    self.assertEqual([t.name for t in housekeeping.unused_tags()], ['Advertisement', 'Boeken'])
    self.assertEqual([p.name for p in housekeeping.unused_places()], ['Nieuw Guinea'])
    html = self.client.get('/dashboard/housekeeping/').content.decode()
    self.assertIn('Advertisement', html)
    self.assertIn('Nieuw Guinea', html)

  def test_delete_after_confirmation_and_recheck(self):
    from core.models import Tag
    confirm = self.client.post('/dashboard/housekeeping/', {'action': 'tags', 'object': [self.old_category.token]})
    self.assertContains(confirm, 'Advertisement')                                  # the confirmation page
    self.assertTrue(Tag.objects.filter(pk=self.old_category.pk).exists())
    Content.objects.create(name='Advertentie', kind='document', user=self.staff, status='p', visibility='c').tags.add(self.old_category)
    self.client.post('/dashboard/housekeeping/', {'action': 'tags', 'object': [self.old_category.token], 'confirm': '1'})
    self.assertTrue(Tag.objects.filter(pk=self.old_category.pk).exists())         # used in between: kept
    self.client.post('/dashboard/housekeeping/', {'action': 'places', 'object': [self.lone.token], 'confirm': '1'})
    from places.models import Place
    self.assertFalse(Place.objects.filter(pk=self.lone.pk).exists())
    self.assertTrue(LogEntry.objects.filter(change_message__contains='housekeeping (unused)').exists())

  def test_needs_the_delete_permission(self):
    self.staff.user_permissions.remove(Permission.objects.get(codename='delete_place'))
    staff = get_user_model().objects.get(pk=self.staff.pk)
    client = Client()
    client.force_login(staff)
    self.assertEqual(client.post('/dashboard/housekeeping/', {'action': 'places', 'object': [self.lone.token], 'confirm': '1'}).status_code, 404)
    html = client.get('/dashboard/housekeeping/').content.decode().replace('"', '')
    self.assertNotIn(f'value={self.lone.token}', html)                            # listed, without a checkbox
    self.assertIn('Nieuw Guinea', html)
