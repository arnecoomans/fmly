import io
import json
import shutil
import tempfile

from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.test import Client, TestCase, override_settings
from PIL import Image

from content.models import Content, Portrait
from people.models import Person

MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=MEDIA, SENDFILE_ROOT=MEDIA, SENDFILE_BACKEND='django_sendfile.backends.simple')
class PortraitEditingTests(TestCase):
  """A photo as someone's portrait (Content.set_portrait, on the photo's
  page) and its crop (PersonPortraitForm, on the person's page)."""

  @classmethod
  def tearDownClass(cls):
    super().tearDownClass()
    shutil.rmtree(MEDIA, ignore_errors=True)

  def setUp(self):
    self.editor = self.user('editor', 'change_content', 'change_person')
    self.client = Client()
    self.client.force_login(self.editor)
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.dee = Person.objects.create(given_name='Adriane', last_name='Bake', user=self.editor, status='p', visibility='c')
    self.passport = self.photo('Paspoort')
    self.group = self.photo('Groep')

  def user(self, name, *perms):
    user = get_user_model().objects.create(username=name)
    for perm in perms:
      user.user_permissions.add(Permission.objects.get(codename=perm))
    user.save()
    return user

  def photo(self, name):
    buffer = io.BytesIO()
    Image.new('RGB', (400, 300), 'white').save(buffer, 'JPEG')
    item = Content.objects.create(name=name, kind='photo', user=self.editor, status='p', visibility='c')
    item.file.save(f'{name}.jpg', ContentFile(buffer.getvalue()))
    return item

  def set_portrait(self, content, person, client=None):
    return (client or self.client).post(f'/api/content/{content.token}/set_portrait/', json.dumps({'token': person.token}), content_type='application/json')

  def crop(self, **fields):
    self.dee.refresh_from_db()
    data = {'_modified': self.dee.date_modified.isoformat(), **{f'portrait-{k}': v for k, v in fields.items()}}
    return self.client.post(f'/api/person/{self.dee.token}/form/portrait/', data)

  def test_set_portrait_links_the_person_and_makes_it_primary(self):
    self.assertEqual(self.set_portrait(self.passport, self.dee).status_code, 200)
    self.assertIn(self.dee, self.passport.people.all())                    # not linked before: linked now
    self.assertEqual(self.dee.primary_portrait_link.content, self.passport)
    self.set_portrait(self.group, self.dee)
    self.assertEqual(Person.objects.get(pk=self.dee.pk).primary_portrait_link.content, self.group)
    self.assertEqual(Portrait.objects.filter(person=self.dee).count(), 2)  # the former one stays, not primary
    self.assertTrue(LogEntry.objects.filter(object_id=str(self.dee.pk), change_message__startswith='Portrait:').exists())

  def test_only_a_photo_and_a_visible_person(self):
    document = Content.objects.create(name='Brief', kind='document', user=self.editor, status='p', visibility='c')
    self.assertEqual(self.set_portrait(document, self.dee).status_code, 400)
    hidden = Person.objects.create(given_name='Verborgen', user=self.user('other'), status='p', visibility='q')
    self.assertEqual(self.set_portrait(self.passport, hidden).status_code, 400)

  def test_crop_and_reset(self):
    self.set_portrait(self.passport, self.dee)
    form = self.client.get(f'/api/person/{self.dee.token}/form/portrait/').json()['html'].replace('"', '')
    self.assertIn('data-viewer-crop', form)
    self.assertIn(f'/content/{self.passport.token}/thumb/large/', form)
    response = self.crop(crop_x='0.1', crop_y='0.2', crop_w='0.3', crop_h='0.4')
    self.assertEqual(response.status_code, 200)
    portrait = Portrait.objects.get(person=self.dee, is_primary=True)
    self.assertEqual(portrait.crop_box, (0.1, 0.2, 0.3, 0.4))
    self.assertIn(f'?v={portrait.version}', response.json()['html'])      # the avatar reloads with the new crop
    self.assertEqual(self.crop(crop_x='0.8', crop_y='0', crop_w='0.5', crop_h='0.5').status_code, 400)   # outside the photo
    self.assertEqual(self.crop(crop_x='0.1', crop_y='0.2', crop_w='0.3', crop_h='0.4', reset='1').status_code, 200)
    self.assertEqual(Portrait.objects.get(person=self.dee, is_primary=True).crop_box, (0, 0, 1, 1))   # the whole photo, explicitly

  def test_no_portrait_no_crop(self):
    self.assertEqual(self.client.get(f'/api/person/{self.dee.token}/form/portrait/').status_code, 404)
    html = self.client.get(self.dee.get_absolute_url()).content.decode().replace('"', '')
    self.assertNotIn('data-cmnsd-edit-name=portrait', html)
    self.set_portrait(self.passport, self.dee)
    html = self.client.get(self.dee.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-edit-dialog=Portrait', html)

  def test_needs_both_permissions(self):
    content_only = Client()
    content_only.force_login(self.user('fotograaf', 'change_content'))
    self.assertEqual(self.set_portrait(self.passport, self.dee, content_only).status_code, 403)
    self.assertFalse(Portrait.objects.exists())

  def test_marker_on_the_photo_page(self):
    other = Person.objects.create(given_name='Eric', user=self.editor, status='p', visibility='c')
    self.passport.people.add(other)
    self.set_portrait(self.passport, self.dee)
    html = self.client.get(self.passport.get_absolute_url()).content.decode()
    self.assertEqual(html.count('person-row__portrait'), 1)                 # Adriane's row, not Eric's
    self.set_portrait(self.group, self.dee)
    self.assertNotIn('person-row__portrait', self.client.get(self.passport.get_absolute_url()).content.decode())


  def test_rotation(self):
    from content.crop import upright_box
    self.set_portrait(self.passport, self.dee)
    self.assertEqual(self.crop(crop_x='0', crop_y='0', crop_w='0.5', crop_h='0.25', rotation='90').status_code, 200)
    portrait = Portrait.objects.get(person=self.dee, is_primary=True)
    self.assertEqual(portrait.rotation, 90)
    self.assertTrue(portrait.version.endswith('-r90'))                     # a new avatar URL
    self.assertEqual(upright_box(portrait.crop_box, 90), (0, 0.5, 0.25, 0.5))   # top-left of the turned photo = bottom-left of the upright one
    self.crop(crop_x='0', crop_y='0', crop_w='0.5', crop_h='0.25', rotation='90', reset='1')
    portrait.refresh_from_db()
    self.assertEqual((portrait.crop_box, portrait.rotation), ((0, 0, 1, 1), 90))   # "whole photo" keeps the turn
    self.assertEqual(self.crop(rotation='45').status_code, 400)            # quarter turns only

  def test_turned_avatar_is_turned(self):
    """The avatar of a turned portrait: a tall image, its top half kept and
    turned 90 degrees - the dark part ends up on the right."""
    buffer = io.BytesIO()
    image = Image.new('RGB', (200, 400), 'white')
    image.paste((0, 0, 0), (0, 0, 200, 200))   # top half dark
    image.save(buffer, 'JPEG')
    tall = Content.objects.create(name='Staand', kind='photo', user=self.editor, status='p', visibility='c')
    tall.file.save('staand.jpg', ContentFile(buffer.getvalue()))
    self.set_portrait(tall, self.dee)
    self.crop(rotation='90')                                               # whole photo, turned: dark half on the right
    response = self.client.get(f'/content/{tall.token}/portrait/{self.dee.token}/')
    self.assertEqual(response.status_code, 200)
    avatar = Image.open(io.BytesIO(b''.join(response.streaming_content) if hasattr(response, 'streaming_content') else response.content)).convert('L')
    width, height = avatar.size
    left, right = avatar.getpixel((width // 8, height // 2)), avatar.getpixel((width * 7 // 8, height // 2))
    self.assertGreater(left, right)                                        # light left, dark right


  def test_a_document_portrait_stays_after_whole_photo(self):
    """A portrait from a document is only used with a crop: "whole photo"
    must not hide it - and the pencil stays even when it isn't used."""
    document = self.photo('Paspoortpagina')
    Content.objects.filter(pk=document.pk).update(kind='document')
    self.set_portrait(Content.objects.get(pk=document.pk), self.dee)
    html = self.client.get(self.dee.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-edit-name=portrait', html)                  # no crop yet, not on the avatar - but croppable
    self.crop(crop_x='0.2', crop_y='0.2', crop_w='0.2', crop_h='0.2', reset='1')
    self.assertIn('/portrait/', self.client.get(self.dee.get_absolute_url()).content.decode())   # the avatar uses it


  def test_choose_from_tagged_photos(self):
    """The dialog lists the images the person is tagged in (current first),
    and saving with another one makes that the portrait, with its crop."""
    self.passport.people.add(self.dee)
    self.group.people.add(self.dee)
    hidden = self.photo('Verborgen')
    Content.objects.filter(pk=hidden.pk).update(visibility='q', user=self.user('ander'))
    hidden.people.add(self.dee)
    self.set_portrait(self.passport, self.dee)
    form = self.client.get(f'/api/person/{self.dee.token}/form/portrait/').json()['html'].replace('"', '')
    self.assertLess(form.index(f'value={self.passport.token}'), form.index(f'value={self.group.token}'))   # current first
    self.assertNotIn(hidden.token, form)                                   # only what this viewer may see
    response = self.crop(photo=self.group.token, crop_x='0.1', crop_y='0.1', crop_w='0.5', crop_h='0.5', rotation='0')
    self.assertEqual(response.status_code, 200)
    primary = Portrait.objects.get(person=self.dee, is_primary=True)
    self.assertEqual((primary.content, primary.crop_box), (self.group, (0.1, 0.1, 0.5, 0.5)))
    self.assertIn(f'/content/{self.group.token}/portrait/', response.json()['html'])   # the avatar follows
    self.assertEqual(Portrait.objects.filter(person=self.dee).count(), 2)  # the passport stays a portrait
    self.assertEqual(self.crop(photo=hidden.token).status_code, 400)      # not offered: refused

  def test_first_portrait_from_the_page(self):
    """No portrait yet, tagged in a photo: the pencil, and saving makes it the portrait."""
    self.group.people.add(self.dee)
    html = self.client.get(self.dee.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-cmnsd-edit-name=portrait', html)
    self.assertEqual(self.crop(crop_x='0', crop_y='0', crop_w='1', crop_h='1').status_code, 200)
    self.assertEqual(Portrait.objects.get(person=self.dee, is_primary=True).content, self.group)

  def test_without_a_portrait_the_dialog_starts_on_a_photo(self):
    from people.forms import PersonPortraitForm
    document = Content.objects.create(name='Paspoortpagina', kind='document', user=self.editor, status='p', visibility='c', year=1900)
    buffer = io.BytesIO()
    Image.new('RGB', (40, 30), 'white').save(buffer, 'JPEG')
    document.file.save('paspoort.jpg', ContentFile(buffer.getvalue()))
    for item in (document, self.group):
      item.people.add(self.dee)
    images = [document, self.group]                                       # oldest first, as the strip
    self.assertEqual(PersonPortraitForm._first_choice(images), self.group.token)
