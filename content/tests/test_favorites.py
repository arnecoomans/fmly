import json

from django.contrib.auth import get_user_model
from django.test import Client, RequestFactory, TestCase

from cmnsd.ui.state import set_sort
from content.models import Content
from content.templatetags.content_tags import in_list_order, mark_wholes
from core import favorites
from core.models import Favorite


class FavoriteTests(TestCase):
  """Favorites (core.models.Favorite, issue #453): the toggle, the heart,
  the lists and the sort."""

  def setUp(self):
    User = get_user_model()
    self.ann = User.objects.create(username='ann', first_name='Ann', last_name='Bake')
    self.bob = User.objects.create(username='bob', first_name='Bob', last_name='Coomans')
    self.item = Content.objects.create(name='Trouwfoto', user=self.ann, status='p', visibility='p')

  def client_for(self, user=None):
    client = Client()
    if user:
      client.force_login(user)
    return client

  def toggle(self, user, item=None):
    item = item or self.item
    return self.client_for(user).post(f'/api/content/{item.token}/toggle_favorite/', json.dumps({}), content_type='application/json')

  def request_for(self, user):
    request = RequestFactory().get('/')
    request.user = user
    request.session = {}
    return request

  # --- the toggle ---

  def test_toggle_adds_and_removes(self):
    response = self.toggle(self.ann)
    self.assertEqual(response.status_code, 200)
    self.assertEqual(Favorite.objects.get().user, self.ann)
    self.assertIn('bi-heart-fill', response.json()['html'])   # the heart again, now yours
    self.toggle(self.ann)
    self.assertFalse(Favorite.objects.exists())

  def test_one_per_user(self):
    self.toggle(self.ann)
    self.toggle(self.bob)
    self.assertEqual(Favorite.objects.count(), 2)
    self.assertEqual(favorites.counts([self.item]), {self.item.pk: 2})

  def test_signed_out_is_403(self):
    self.assertEqual(self.toggle(None).status_code, 403)

  def test_draft_cannot_be_favorited(self):
    draft = Content.objects.create(name='Klad', user=self.ann, status='c', visibility='c')
    self.assertEqual(self.toggle(self.ann, draft).status_code, 400)
    self.assertFalse(Favorite.objects.exists())

  def test_cannot_favorite_what_you_cannot_see(self):
    private = Content.objects.create(name='Privé', user=self.ann, status='p', visibility='q')
    self.assertEqual(self.toggle(self.bob, private).status_code, 404)

  # --- the heart on the item page ---

  def test_names_only_for_who_is_signed_in(self):
    Favorite.objects.create(user=self.bob, target=self.item)
    url = self.item.get_absolute_url()
    signed_in = self.client_for(self.ann).get(url).content.decode()
    self.assertIn('Bob Coomans', signed_in)
    self.assertIn('toggle_favorite', signed_in)
    signed_out = self.client_for().get(url).content.decode()
    self.assertNotIn('Bob Coomans', signed_out)
    self.assertNotIn('toggle_favorite', signed_out)
    self.assertIn('favorite__count', signed_out)   # the count, at most

  def test_heart(self):
    Favorite.objects.create(user=self.bob, target=self.item)
    heart = favorites.heart(self.item, self.request_for(self.bob))
    self.assertEqual((heart['count'], heart['mine'], heart['names']), (1, True, ['Bob Coomans']))

  # --- cards ---

  def test_cards_count_in_one_query(self):
    other = Content.objects.create(name='Paspoort', user=self.ann, status='p', visibility='p')
    Favorite.objects.create(user=self.bob, target=self.item)
    Favorite.objects.create(user=self.ann, target=self.item)
    items = favorites.attach([self.item, other], self.request_for(self.ann))
    self.assertEqual([(i.favorite_count, i.is_favorite) for i in items], [(2, True), (0, False)])
    with self.assertNumQueries(3):   # parts, transcripts, favorites
      mark_wholes([self.item, other], self.request_for(self.ann))

  # --- the lists ---

  def test_my_favorites_newest_first_and_only_visible(self):
    second = Content.objects.create(name='Paspoort', user=self.ann, status='p', visibility='p')
    Favorite.objects.create(user=self.bob, target=self.item)
    Favorite.objects.create(user=self.bob, target=second)
    self.assertEqual(favorites.my_favorites(self.request_for(self.bob)), [second, self.item])
    Content.objects.filter(pk=second.pk).update(visibility='q')   # hidden from Bob since
    self.assertEqual(favorites.my_favorites(self.request_for(self.bob)), [self.item])

  def test_my_favorites_page(self):
    Favorite.objects.create(user=self.bob, target=self.item)
    page = self.client_for(self.bob).get('/content/favorites/')
    self.assertContains(page, 'Trouwfoto')
    self.assertEqual(self.client_for().get('/content/favorites/').status_code, 302)   # sign in first

  def test_family_favorites_most_first(self):
    second = Content.objects.create(name='Paspoort', user=self.ann, status='p', visibility='p')
    Content.objects.create(name='Niemand', user=self.ann, status='p', visibility='p')   # no favorites: not listed
    Favorite.objects.create(user=self.bob, target=self.item)
    Favorite.objects.create(user=self.bob, target=second)
    Favorite.objects.create(user=self.ann, target=second)
    found = favorites.family_favorites(self.request_for(self.ann))
    self.assertEqual([(i.name, i.favorite_count) for i in found], [('Paspoort', 2), ('Trouwfoto', 1)])
    self.assertContains(self.client_for(self.ann).get('/'), 'Paspoort')

  # --- the sort ---

  def test_most_favorited_sort(self):
    second = Content.objects.create(name='Paspoort', user=self.ann, status='p', visibility='p')
    Favorite.objects.create(user=self.bob, target=second)
    ordered = Content.objects.filter(pk__in=[self.item.pk, second.pk]).in_order('favorites')
    self.assertEqual(list(ordered), [second, self.item])
    request = self.request_for(self.ann)
    set_sort(request, 'content.list', 'favorites')
    self.assertEqual(in_list_order([self.item, second], request), [second, self.item])
