from django.contrib.auth import get_user_model
from django.test import TestCase

from content.models import Content


class ContentUrlTests(TestCase):
  """content/<token>/<slug>/ - the token finds the item, the slug is for
  reading; token-only and outdated-slug URLs redirect."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    self.item = Content.objects.create(name='Zorgkosten geboorte Eric', user=self.user, status='p', visibility='c')

  def test_readable_url(self):
    self.assertEqual(self.item.get_absolute_url(), f'/content/{self.item.token}/zorgkosten-geboorte-eric/')
    self.assertEqual(self.client.get(self.item.get_absolute_url()).status_code, 200)

  def test_token_only_and_outdated_slug_redirect(self):
    for url in (f'/content/{self.item.token}/', f'/content/{self.item.token}/een-oude-naam/'):
      self.assertRedirects(self.client.get(url), self.item.get_absolute_url(), status_code=301)

  def test_links_survive_a_rename(self):
    old = self.item.get_absolute_url()
    self.item.name = 'Rekening Petronella-hospitaal'
    self.item.save()
    self.assertRedirects(self.client.get(old), f'/content/{self.item.token}/rekening-petronella-hospitaal/', status_code=301)

  def test_hidden_item_404s_without_revealing_its_slug(self):
    self.client.logout()
    response = self.client.get(f'/content/{self.item.token}/')
    self.assertEqual(response.status_code, 404)
    self.assertNotIn('Location', response)

  def test_reserved_words_never_become_slugs(self):
    item = Content.objects.create(name='File', user=self.user)
    self.assertEqual(item.slug, 'file-2')
    self.assertNotEqual(item.get_absolute_url(), f'/content/{item.token}/file/')
