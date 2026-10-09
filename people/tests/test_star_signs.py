from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import Preferences
from events.models import Event
from people.models import Person
from people.star_signs import star_sign


class StarSignTests(TestCase):
  """Preferences.superstitious: a star sign badge on a person's page, from
  an exact birth date (people/star_signs.py)."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.user.save()
    self.client.force_login(self.user)
    self.person = Person.objects.create(given_name='Corry', user=self.user, status='p', visibility='c')
    self.birth = Event.objects.create(kind=Event.Kind.BIRTH, year=1917, month=4, day=16, user=self.user)
    self.birth.people.add(self.person)

  def superstitious(self, value=True):
    Preferences.objects.update_or_create(user=self.user, defaults={'superstitious': value})

  def page(self):
    """The badge as the page gets it: loaded after it's shown, through the
    API (person/functions/get_star_sign.html)."""
    response = self.client.get(f'/api/person/{self.person.token}/get_star_sign/').json()
    return response['fields']['get_star_sign'] or ''

  def test_signs_and_their_edges(self):
    name = lambda month, day: str(star_sign(month, day)['name'])
    self.assertEqual(name(1, 1), 'Capricorn')                 # across the new year
    self.assertEqual(name(1, 19), 'Capricorn')
    self.assertEqual(name(1, 20), 'Aquarius')
    self.assertEqual(name(3, 20), 'Pisces')
    self.assertEqual(name(3, 21), 'Aries')
    self.assertEqual(name(4, 16), 'Aries')
    self.assertEqual(name(12, 21), 'Sagittarius')
    self.assertEqual(name(12, 22), 'Capricorn')

  def test_loaded_after_the_page(self):
    from django.test import override_settings
    self.superstitious()
    html = self.client.get(self.person.get_absolute_url()).content.decode().replace('"', '')
    self.assertIn('data-field=get_star_sign', html)          # a placeholder, filled through the API
    self.assertNotIn('person-star-sign', html)
    with override_settings(CMNSD_LOAD_ON_READY=False):       # deferred loading off: in the page itself
      self.assertIn('person-star-sign', self.client.get(self.person.get_absolute_url()).content.decode())

  def test_badge_only_for_the_superstitious(self):
    self.assertNotIn('person-star-sign', self.page())        # off by default
    self.superstitious()
    html = self.page()
    self.assertIn('person-star-sign', html)
    self.assertIn('Aries', html)

  def test_only_from_an_exact_full_date(self):
    self.superstitious()
    Event.objects.filter(pk=self.birth.pk).update(date_qualifier='circa')
    self.assertNotIn('person-star-sign', self.page())
    Event.objects.filter(pk=self.birth.pk).update(date_qualifier='exact', day=None)   # a month alone
    self.assertNotIn('person-star-sign', self.page())

  def test_set_in_preferences(self):
    self.client.post('/preferences/', {'language': '', 'superstitious': 'on'})
    self.assertTrue(Preferences.objects.get(user=self.user).superstitious)
    self.assertIn('Aries', self.page())
