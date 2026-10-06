import json
from datetime import datetime, timezone

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from content.models import Content


class ContentListTests(TestCase):
  """/content/ (ContentListView) and its live search (api/content/)."""

  def setUp(self):
    self.user = get_user_model().objects.create(username='member')
    self.client.force_login(self.user)
    def item(name, year, added, **fields):
      c = Content.objects.create(name=name, year=year, user=self.user, status='p', visibility='c', **fields)
      Content.objects.filter(pk=c.pk).update(date_created=datetime(added, 1, 1, tzinfo=timezone.utc))
      return c
    self.old = item('Krangan 1992', 1992, 2020)
    self.new = item('Postkaart', 2000, 2026)
    self.back = item('Achterkant', None, 2026)
    self.new.make_parts_of([self.back])

  def names(self, query=''):
    return [c.name for c in self.client.get('/content/' + query).context['content_list']]

  def postcard_first(self):
    html = self.client.get('/content/').content.decode()
    return html.index('Postkaart') < html.index('Krangan 1992')

  def test_lists_wholes_only(self):
    self.assertEqual(set(self.names()), {'Krangan 1992', 'Postkaart'})

  def test_search_page_and_api_agree(self):
    self.assertEqual(self.names('?q=krangan'), ['Krangan 1992'])
    data = json.loads(self.client.get('/api/content/', {'q': 'krangan'}).content)
    self.assertEqual(data['count'], 1)
    self.assertIn('Krangan 1992', data['html'])

  def test_remembered_sort_applies(self):
    # Postkaart: from 2000, added 2026. Krangan: from 1992, added 2020.
    self.assertTrue(self.postcard_first())            # recently added (default): Postkaart first
    self.client.post('/ui/sort/', json.dumps({'key': 'content.list', 'value': 'date'}), content_type='application/json')
    self.assertFalse(self.postcard_first())           # chronologically: Krangan (1992) first


class PartsBadgeTests(TestCase):
  """A card for an item with parts gets .content-card--has-parts and a
  count badge (the grid's mark_wholes) - only for parts this viewer may
  see."""

  def setUp(self):
    from django.contrib.auth import get_user_model
    self.user = get_user_model().objects.create(username='member')
    self.other = get_user_model().objects.create(username='other')
    self.client.force_login(self.user)
    make = lambda name, owner, visibility='c': Content.objects.create(name=name, kind='photo', user=owner, status='p', visibility=visibility)
    self.book = make('Boek', self.user)
    self.book.make_parts_of([make('Pagina', self.user)])
    self.loose = make('Losse foto', self.user)
    self.hidden_whole = make('Met geheim deel', self.user)
    self.hidden_whole.make_parts_of([make('Geheim', self.other, visibility='q')])   # private to its owner

  def card_classes(self):
    import re
    html = self.client.get('/content/').content.decode().replace('"', '')
    return {name: classes for classes, name in re.findall(r'<a class=(content-card[^ >]*(?: content-card--[\w-]+)*)[^>]*>.*?content-card__title>([^<]+)<', html, re.S)}

  def test_only_wholes_with_visible_parts_are_marked(self):
    classes = self.card_classes()
    self.assertIn('content-card--has-parts', classes['Boek'])
    self.assertNotIn('content-card--has-parts', classes['Losse foto'])
    self.assertNotIn('content-card--has-parts', classes['Met geheim deel'])

  def test_badge_counts_the_whole_and_its_visible_parts(self):
    html = self.client.get('/content/').content.decode().replace('"', '')
    self.assertEqual(html.count('class=content-card__parts-badge'), 1)   # only Boek
    self.assertRegex(html, r'content-card__parts-badge[^>]*><i class=bi bi-stack></i>2<')

  def test_badge_not_inflated_by_the_viewers_family(self):
    # The visibility filter joins the viewer's family list - a viewer with
    # several family members must not multiply the count.
    from django.contrib.auth import get_user_model
    Preferences = get_user_model().preferences.related.related_model
    preferences = Preferences.objects.create(user=self.user)
    preferences.family.add(self.other, get_user_model().objects.create(username='third'))
    self.book.make_parts_of([*self.book.parts.all(), Content.objects.create(name='Pagina 2', kind='photo', user=self.user, status='p', visibility='f')])
    html = self.client.get('/content/').content.decode().replace('"', '')
    self.assertRegex(html, r'content-card__parts-badge[^>]*><i class=bi bi-stack></i>3<')


class TranscriptBadgeTests(TestCase):
  """The content card's transcript sign (the grid's mark_wholes): own
  transcripts, transcripts on visible pages, incomplete outlined."""

  def setUp(self):
    from django.contrib.auth import get_user_model
    self.user = get_user_model().objects.create(username='member')
    self.other = get_user_model().objects.create(username='other')
    self.client.force_login(self.user)
    make = lambda name, owner=None, visibility='c': Content.objects.create(name=name, kind='document', user=owner or self.user, status='p', visibility=visibility)
    self.letter = make('Brief')
    self.book = make('Boek')
    self.page = make('Bladzijde')
    self.secret_page = make('Geheime bladzijde', owner=self.other, visibility='q')
    self.book.make_parts_of([self.page, self.secret_page])
    self.plain = make('Zonder tekst')

  def transcript(self, item, language='nl', **fields):
    from content.models import Transcript
    return Transcript.objects.create(content=item, language=language, text='tekst', **fields)

  def cards(self):
    import re
    html = self.client.get('/content/').content.decode().replace('"', '')
    return {name: card for card, name in re.findall(r'(<a class=content-card.*?content-card__title>([^<]+)<)', html, re.S)}

  def test_own_transcript_with_languages(self):
    self.transcript(self.letter)
    self.transcript(self.letter, 'en', kind='translation')
    card = self.cards()['Brief']
    self.assertIn('content-card__transcript', card)
    self.assertIn('Transcript: Dutch, English', card)
    self.assertNotIn('content-card__transcript', self.cards()['Zonder tekst'])

  def test_transcribed_pages_count_on_the_whole_hidden_ones_not(self):
    self.transcript(self.page)
    self.transcript(self.secret_page)
    card = self.cards()['Boek']
    self.assertIn('Transcribed on 1 page', card)                            # the hidden page's transcript doesn't count

  def test_incomplete_is_outlined(self):
    self.transcript(self.letter, incomplete=True)
    card = self.cards()['Brief']
    self.assertIn('content-card__transcript is-incomplete', card)
    self.assertIn('(incomplete)', card)

  def test_two_queries_for_the_whole_list(self):
    from django.test import RequestFactory
    from content.templatetags.content_tags import mark_wholes
    request = RequestFactory().get('/')
    request.user = self.user
    items = list(Content.objects.filter(parent__isnull=True))
    with self.assertNumQueries(2):
      mark_wholes(items, request)
