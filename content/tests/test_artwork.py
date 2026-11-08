from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, RequestFactory, TestCase

from content.models import Content, ContentPerson
from content.roles import suggested_role
from people.templatetags.tags import type_counts


class ArtworkTests(TestCase):
  """An artwork - a painting, drawing, miniature - is a picture like a
  photo (Content.PICTURES): a photo's kinds, labelled "kind of picture";
  a painted portrait suggests subject; it counts where pictures do."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='redacteur')
    self.user.user_permissions.add(Permission.objects.get(codename='change_content'))
    self.user.save()
    self.client = Client()
    self.client.force_login(self.user)
    self.painting = Content.objects.create(name='Portret van William Archibald Bake', kind='artwork', user=self.user, status='p', visibility='c')

  def make_portrait(self, item):
    item.ensure_detail()
    item.photo_detail.photo_kind = 'portrait'
    item.photo_detail.save()

  def test_a_photos_kinds_as_kind_of_picture(self):
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    html = self.client.get(self.painting.get_absolute_url()).content.decode()
    self.assertIn('Kind of picture', html)
    self.assertIn('Posed, one person', html)
    self.painting.refresh_from_db()
    response = self.client.post(f'/api/content/{self.painting.token}/form/photo_kind/', {'_modified': self.painting.date_modified.isoformat(), 'photo_kind-photo_kind': 'portrait'})
    self.assertEqual(response.status_code, 200)
    self.assertEqual(Content.objects.get(pk=self.painting.pk).get_detail().photo_kind, 'portrait')

  def test_explained_on_its_button(self):
    self.client.post('/ui/edit/', {'on': '1', 'next': '/'})
    self.assertIn('Made by hand: a painting, drawing', self.client.get(self.painting.get_absolute_url()).content.decode())

  def test_a_painted_portrait_suggests_subject(self):
    self.make_portrait(self.painting)
    self.assertEqual(suggested_role(Content.objects.get(pk=self.painting.pk)), ContentPerson.Role.SUBJECT)

  def test_its_own_type_pills(self):
    self.make_portrait(self.painting)
    other = Content.objects.create(name='Familie', kind='artwork', user=self.user, status='p', visibility='c')
    other.ensure_detail()
    other.photo_detail.photo_kind = 'group'
    other.photo_detail.save()
    items = list(Content.objects.filter(kind='artwork').select_related('photo_detail'))
    self.assertEqual([(kind, count) for kind, count, _ in type_counts(items)], [('artwork', 2)])

  def test_without_people_is_a_loose_end(self):
    from dashboard.blocks import _loose_end_queryset
    request = RequestFactory().get('/')
    request.user = self.user
    self.assertIn(self.painting, _loose_end_queryset('photos-without-people', request))

  def test_a_painted_portrait_first_for_a_portrait(self):
    from people.forms import PersonPortraitForm
    snapshot = Content.objects.create(name='Kiekje', kind='photo', user=self.user, status='p', visibility='c')
    self.make_portrait(self.painting)
    images = [snapshot, Content.objects.get(pk=self.painting.pk)]                # the oldest first
    self.assertEqual(PersonPortraitForm._first_choice(images), self.painting.token)
