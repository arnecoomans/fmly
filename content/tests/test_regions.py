from importlib import import_module

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from content.models import Content, ContentPerson, Portrait
from people.models import Person


class RegionTests(TestCase):
  """A frame on a person's link to a photo (cmnsd RegionMixin, issue #480):
  a box as fractions of the image as shown - whole, and within it."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='regions')
    self.photo = Content.objects.create(name='Kerstfeest', kind='photo', user=self.user, status='p', visibility='c')
    self.ida = Person.objects.create(given_name='Ida', user=self.user, status='p', visibility='c')
    self.photo.people.add(self.ida)
    self.link = ContentPerson.objects.get(content=self.photo, person=self.ida)

  def test_set_and_read(self):
    self.assertIsNone(self.link.region)
    self.link.set_region((0.41234567, 0.1, 0.12, 0.18))
    self.link.full_clean()
    self.assertEqual(self.link.region, (0.4123, 0.1, 0.12, 0.18))
    self.assertFalse(self.link.region_is_point)
    self.link.set_region((0.5, 0.5, 0, 0))
    self.assertTrue(self.link.region_is_point)                                  # a point: "this spot"
    self.link.set_region(None)
    self.assertFalse(self.link.has_region)

  def test_whole_and_within(self):
    self.link.region_x = 0.2
    with self.assertRaises(ValidationError):
      self.link.full_clean()                                                     # all four or none
    self.link.set_region((0.9, 0.1, 0.2, 0.1))
    with self.assertRaises(ValidationError):
      self.link.full_clean()                                                     # past the right edge
    self.link.set_region((0.8, 0.1, 0.2, 0.1))
    self.link.full_clean()                                                       # right up to it


class FramesFromPortraitsTests(TestCase):
  """The migration's seeding: each portrait crop becomes that person's frame
  on that photo - a turned one mapped back to the photo as shown."""

  def test_seed(self):
    seed = import_module('content.migrations.0007_contentperson_region').frames_from_portraits
    user = get_user_model().objects.create(username='seed')
    photo = Content.objects.create(name='Groep', kind='photo', user=user, status='p', visibility='c')
    upright = Person.objects.create(given_name='Recht', user=user, status='p', visibility='c')
    turned = Person.objects.create(given_name='Gedraaid', user=user, status='p', visibility='c')
    Portrait.objects.create(person=upright, content=photo, crop_x=0.1, crop_y=0.2, crop_w=0.3, crop_h=0.25)
    Portrait.objects.create(person=turned, content=photo, crop_x=0.5, crop_y=0.0, crop_w=0.2, crop_h=0.1, rotation=90)
    photo.people.add(upright)                                                    # the turned one isn't linked yet
    seed(apps, None)
    self.assertEqual(ContentPerson.objects.get(content=photo, person=upright).region, (0.1, 0.2, 0.3, 0.25))
    link = ContentPerson.objects.get(content=photo, person=turned)                # linked now, without a role
    self.assertEqual(link.role, '')
    self.assertEqual(link.region, (0.0, 0.3, 0.1, 0.2))                         # turned back: w and h swap


class FramesShownTests(TestCase):
  """Who is where, on a photo's page: a frame per person with one, placed
  in percent; the name; doubt for possibly depicted; none for a person the
  viewer may not see; the remembered switch."""

  def setUp(self):
    from django.test import Client
    self.user = get_user_model().objects.create(username='shown', is_staff=True)
    self.user.save()
    self.photo = Content.objects.create(name='Kerstfeest', kind='photo', file='content/kerst.jpg', user=self.user, status='p', visibility='c')
    self.ida = Person.objects.create(given_name='Ida', user=self.user, status='p', visibility='c')
    self.winke = Person.objects.create(given_name='Winke', user=self.user, status='p', visibility='c')
    self.photo.people.add(self.ida, self.winke)
    self.frame(self.ida, (0.1, 0.2, 0.15, 0.2))
    self.frame(self.winke, (0.5, 0.25, 0.12, 0.18), role='possibly_depicted')
    self.client = Client()
    self.client.force_login(self.user)

  def frame(self, person, box, role=''):
    link = ContentPerson.objects.get(content=self.photo, person=person)
    link.set_region(box)
    link.role = role
    link.save()

  def page(self, client=None):
    return (client or self.client).get(self.photo.get_absolute_url()).content.decode().replace('"', '')

  def test_frames_and_names(self):
    html = self.page()
    for part in ('left:10%', 'top:20%', 'width:15%', 'height:20%'):            # placed in percent (the minifier compacts the style)
      self.assertIn(part, html)
    self.assertIn('>Ida</span>', html)
    self.assertIn('>Winke?</span>', html)                                      # possibly depicted: the doubt
    self.assertLess(html.index('>Ida</span>'), html.index('>Winke?</span>'))  # largest first: the smaller on top
    self.assertIn(f'data-cmnsd-region-for={self.ida.token}', html)            # the card, linked to its frame
    self.assertIn('data-cmnsd-filter-save=content.frames', html)              # the switch

  def test_hidden_person_no_frame(self):
    from django.test import Client
    self.winke.visibility = 'q'
    self.winke.user = get_user_model().objects.create(username='other')
    self.winke.save()
    reader = get_user_model().objects.create(username='reader')
    reader.save()
    client = Client()
    client.force_login(reader)
    html = self.page(client)
    self.assertIn('>Ida</span>', html)
    self.assertNotIn('Winke', html)                                            # no frame telling what the card hides


class PortraitGivesFrameTests(TestCase):
  """A portrait crop saved after the seeding gives the person a frame on
  that photo - unless they have one already."""

  def test_crop_gives_frame(self):
    user = get_user_model().objects.create(username='crop')
    photo = Content.objects.create(name='Albert en Nettie', kind='photo', user=user, status='p', visibility='c')
    albert = Person.objects.create(given_name='Albert', user=user, status='p', visibility='c')
    photo.people.add(albert)
    portrait = Portrait.objects.create(person=albert, content=photo)
    self.assertIsNone(ContentPerson.objects.get(content=photo, person=albert).region)   # no crop: no frame
    portrait.crop_x, portrait.crop_y, portrait.crop_w, portrait.crop_h = 0.55, 0.19, 0.15, 0.11
    portrait.save()
    link = ContentPerson.objects.get(content=photo, person=albert)
    self.assertEqual(link.region, (0.55, 0.19, 0.15, 0.11))
    link.set_region((0.5, 0.1, 0.3, 0.6))                                         # drawn by hand, larger
    link.save()
    portrait.crop_x = 0.56
    portrait.save()
    self.assertEqual(ContentPerson.objects.get(content=photo, person=albert).region, (0.5, 0.1, 0.3, 0.6))   # left alone


class PointOutTests(TestCase):
  """Edit mode: point someone out on a photo (Content.set_person_region) -
  a box or a point, changed, removed; refused outside the image, for
  someone not on it, on an item without an image, for who may not edit."""

  def setUp(self):
    import json
    from django.contrib.auth.models import Permission
    from django.test import Client
    self.json = json
    self.editor = get_user_model().objects.create(username='pointer', is_staff=True)
    self.editor.user_permissions.add(Permission.objects.get(codename='change_content'))
    self.editor.save()
    self.photo = Content.objects.create(name='Albert en Nettie', kind='photo', file='content/albert.jpg', user=self.editor, status='p', visibility='c')
    self.albert = Person.objects.create(given_name='Albert', user=self.editor, status='p', visibility='c')
    self.photo.people.add(self.albert)
    self.client = Client()
    self.client.force_login(self.editor)

  def point(self, item=None, user=None, **data):
    from django.test import Client
    client = self.client
    if user is not None:
      client = Client()
      client.force_login(user)
    return client.post(f'/api/content/{(item or self.photo).token}/set_person_region/', self.json.dumps({'person': self.albert.token, **data}), content_type='application/json')

  def region(self):
    return ContentPerson.objects.get(content=self.photo, person=self.albert).region

  def test_box_point_and_remove(self):
    self.assertEqual(self.point(region_x='0.5483', region_y='0.1864', region_w='0.1468', region_h='0.1101').status_code, 200)
    self.assertEqual(self.region(), (0.5483, 0.1864, 0.1468, 0.1101))
    self.point(region_x='0.6', region_y='0.3', region_w='0', region_h='0')
    self.assertEqual(self.region(), (0.6, 0.3, 0.0, 0.0))                       # a point
    self.point(clear='1')
    self.assertIsNone(self.region())

  def test_refusals(self):
    self.assertEqual(self.point(region_x='0.9', region_y='0.1', region_w='0.3', region_h='0.1').status_code, 400)   # past the edge
    self.assertEqual(self.point(region_x='zomaar').status_code, 400)
    letter = Content.objects.create(name='Brief', kind='document', user=self.editor, status='p', visibility='c')
    letter.people.add(self.albert)
    self.assertEqual(self.point(item=letter, region_x='0.1', region_y='0.1', region_w='0.1', region_h='0.1').status_code, 400)   # no image
    reader = get_user_model().objects.create(username='reader2')
    reader.save()
    self.assertEqual(self.point(user=reader, region_x='0.1', region_y='0.1', region_w='0.1', region_h='0.1').status_code, 403)
    self.assertIsNone(self.region())

  def test_not_for_who_isnt_in_the_picture(self):
    """Only depicted, possibly depicted or no role yet: not a subject,
    creator, addressee or owner - and a frame kept from before shows again
    when the role comes back."""
    self.point(region_x='0.5', region_y='0.2', region_w='0.1', region_h='0.1')
    for role in ('subject', 'creator'):
      ContentPerson.objects.filter(content=self.photo, person=self.albert).update(role=role)
      self.assertEqual(self.point(region_x='0.4', region_y='0.2', region_w='0.1', region_h='0.1').status_code, 400)
    self.assertNotIn('>Albert</span>', self.client.get(self.photo.get_absolute_url()).content.decode())   # hidden
    ContentPerson.objects.filter(content=self.photo, person=self.albert).update(role='depicted')
    self.assertIn('>Albert</span>', self.client.get(self.photo.get_absolute_url()).content.decode())      # kept, shown again

  def test_controls_in_edit_mode(self):
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    html = self.client.get(self.photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn(f'data-cmnsd-mark=#figure-{self.photo.token}', html)
    self.assertIn('point out', html)
    self.point(region_x='0.5', region_y='0.2', region_w='0.1', region_h='0.1')
    html = self.client.get(self.photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('who-is-where__person has-frame', html)                      # at the photo, not down at People
    self.assertIn('>redraw</button>', html)
    self.assertIn(f'data-cmnsd-filter=#media-{self.photo.token}', html)        # the switch: frames and people alike
    self.assertIn('<ul class=who-is-where__people data-filter-value=frame>', html)
    self.assertIn('>remove</button>', html)


  def test_adding_someone_on_a_photo_reloads(self):
    """They show under the photo too, to point out; elsewhere the card is
    added in place."""
    import re
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    photo = self.client.get(self.photo.get_absolute_url()).content.decode().replace('"', '')
    self.assertRegex(photo, r'data-cmnsd-insert=reload[^>]*data-cmnsd-picker=person|data-cmnsd-picker=person[^>]*data-cmnsd-insert=reload')
    letter = Content.objects.create(name='Brief', kind='document', user=self.editor, status='p', visibility='c')
    page = self.client.get(letter.get_absolute_url()).content.decode().replace('"', '')
    form = re.search(r'<form[^>]*data-cmnsd-picker=person[^>]*>', page).group(0)
    self.assertIn('data-cmnsd-insert=append', form)


class FrameAsPortraitTests(TestCase):
  """Someone pointed out without a portrait: their frame becomes it, cropped
  square around it (content/portraits.py frame_as_portrait)."""

  def test_square_around(self):
    from content.portraits import square_around
    x, y, w, h = square_around((0.5, 0.2, 0.1, 0.15), 2000, 1000)          # a 200 x 150 px face
    self.assertAlmostEqual(w * 2000, h * 1000)                                 # square in pixels
    self.assertAlmostEqual(w * 2000, 280)                                      # 1.4 x its larger side
    self.assertAlmostEqual((x + w / 2) * 2000, 1100)                          # centred on the face
    x, y, w, h = square_around((0.0, 0.0, 0.1, 0.1), 1000, 1000)
    self.assertEqual((x, y), (0.0, 0.0))                                       # kept within the image

  def test_offered_and_made(self):
    import json
    from django.contrib.auth.models import Permission
    from django.test import Client
    editor = get_user_model().objects.create(username='portret', is_staff=True)
    for codename in ('change_content', 'change_person'):
      editor.user_permissions.add(Permission.objects.get(codename=codename))
    editor.save()
    photo = Content.objects.create(name='Familiereunie', kind='photo', file='content/reunie.jpg', width=2000, height=1000, user=editor, status='p', visibility='c')
    bert = Person.objects.create(given_name='Bert', user=editor, status='p', visibility='c')
    photo.people.add(bert)
    link = ContentPerson.objects.get(content=photo, person=bert)
    link.set_region((0.5, 0.2, 0.1, 0.15))
    link.save()
    client = Client()
    client.force_login(editor)
    client.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.assertIn('use as portrait', client.get(photo.get_absolute_url()).content.decode())
    response = client.post(f'/api/content/{photo.token}/frame_as_portrait/', json.dumps({'person': bert.token}), content_type='application/json')
    self.assertEqual(response.status_code, 200, response.content)
    portrait = Portrait.objects.get(person=bert, content=photo)
    self.assertTrue(portrait.is_primary)
    self.assertAlmostEqual(portrait.crop_w * 2000, portrait.crop_h * 1000, places=1)
    self.assertNotIn('use as portrait', client.get(photo.get_absolute_url()).content.decode())   # has one now
