import io
import shutil
import tempfile
from unittest import mock, skipUnless

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import Client, TestCase, override_settings

from content.models import Content, Transcript
from content.transcription import options
from content.transcription.delpher import link_parts, search_terms, select

DELPHER = ('https://www.delpher.nl/nl/kranten/view?query=%22F.+coomans%22&coll=ddd'
           '&identifier=ddd:010956338:mpeg21:a0237&resultsidentifier=ddd:010956338:mpeg21:a0237')


class DelpherParsingTests(TestCase):
  """content/transcription/delpher.py: the link, the search terms, which
  paragraphs are kept."""

  def test_link_parts(self):
    self.assertEqual(link_parts(DELPHER), ('ddd:010956338:mpeg21:a0237', ['f. coomans'], []))
    self.assertEqual(link_parts('https://www.delpher.nl/nl/kranten/view?identifier=ddd:010029786:mpeg21:p012')[0], None)  # a page, not an article
    self.assertEqual(link_parts('https://example.org/x')[0], None)

  def test_search_terms(self):
    self.assertEqual(search_terms('"L. Samson" AND "bake"'), (['l. samson', 'bake'], []))
    self.assertEqual(search_terms('coomans AND geboorte NOT ruiter'), (['coomans', 'geboorte'], ['ruiter']))

  def test_select_prefers_the_paragraph_with_most_terms(self):
    paragraphs = ['Coomans weggeloopen hond', 'astrologie: uur van geboorte', 'Geboren: Coomans, een zoon']
    terms, excluded = search_terms('coomans AND geboren')
    self.assertEqual(select(paragraphs, terms, excluded), ['Geboren: Coomans, een zoon'])
    self.assertEqual(select(['een alinea'], ['x'], []), ['een alinea'])          # one paragraph: all of it
    self.assertEqual(select(['a', 'b'], ['zzz'], []), ['a', 'b'])               # no match: all


class GuessTests(TestCase):
  # Delpher is never reached from a test: fetch_article is replaced where
  # used (content.transcription.delpher), and the cache is cleared so an
  # earlier answer can't leak in.
  """POST content/<token>/transcribe/guess/ and the page's button."""

  def setUp(self):
    from django.core.cache import cache
    cache.clear()
    self.user = get_user_model().objects.create(username='transcriber')
    for perm in ('add_transcript', 'change_transcript'):
      self.user.user_permissions.add(Permission.objects.get(codename=perm))
    self.user.save()
    self.item = Content.objects.create(name='Verlies', kind='document', source=DELPHER, user=self.user, status='p', visibility='c')
    self.client.force_login(self.user)

  def guess(self, **data):
    import json
    return self.client.post(f'/content/{self.item.token}/transcribe/guess/', json.dumps(data), content_type='application/json')

  @mock.patch('content.transcription.delpher.fetch_article', return_value=('Verlies.', ['De heer F. Coomans verloor een portemonnaie.']))
  def test_guess_from_delpher(self, fetch):
    data = self.guess(source='delpher').json()
    self.assertTrue(data['ok'])
    self.assertEqual(data['source']['name'], 'delpher')
    self.assertEqual(data['text'], 'Verlies.\n\nDe heer F. Coomans verloor een portemonnaie.')
    self.assertEqual(data['language'], 'nl')
    fetch.assert_called_once_with('ddd:010956338:mpeg21:a0237')
    self.assertFalse(Transcript.objects.exists())                             # nothing saved by the guess itself

  def test_no_usable_source_is_a_readable_error(self):
    Content.objects.filter(pk=self.item.pk).update(source='')
    response = self.guess(source='delpher')
    self.assertEqual(response.status_code, 422)
    self.assertTrue(response.json()['error'])

  def test_signed_out_gets_json_not_a_redirect(self):
    response = Client().post(f'/content/{self.item.token}/transcribe/guess/', '{}', content_type='application/json')
    self.assertEqual(response.status_code, 403)
    self.assertFalse(response.json()['ok'])

  def test_options_tesseract_disabled_until_installed(self):
    tesseract = next(o for o in options(self.item) if o['name'] == 'tesseract')
    with mock.patch('content.transcription.tesseract.shutil.which', return_value=None):
      tesseract = next(o for o in options(self.item) if o['name'] == 'tesseract')
    self.assertFalse(tesseract['enabled'])

  def test_button_only_while_the_text_is_empty(self):
    html = self.client.get(f'/content/{self.item.token}/transcribe/').content.decode()
    self.assertIn('class=transcribe__guess data-guess-url=', html)
    Transcript.objects.create(content=self.item, kind='original', language='nl', text='Al begonnen')
    html = self.client.get(f'/content/{self.item.token}/transcribe/').content.decode()
    self.assertNotIn('class=transcribe__guess data-guess-url=', html)

  @mock.patch('content.transcription.delpher.fetch_article', return_value=('Verlies.', ['Eerste stuk.', 'Tweede stuk.']))
  def test_delpher_text_on_the_left(self, fetch):
    html = self.client.get(f'/content/{self.item.token}/transcribe/?left=source').content.decode()
    self.assertIn('Tweede stuk.', html)

  def test_a_source_must_be_named(self):
    response = self.guess()
    self.assertEqual(response.status_code, 400)                             # no hidden default
    html = self.client.get(f'/content/{self.item.token}/transcribe/').content.decode()
    self.assertIn('Fetch text from Delpher', html)
    self.assertIn('only the article number from the source link is sent', html)


class MatchTests(TestCase):
  """content/transcription/match.py: the part of a long text an image shows."""

  COLUMN = ('WEGGELOOPEN HOND, reu, wit met bruin, pluimstaart en lange nekharen. Aan te geven bij: '
            'Coomans Emb, Kemiri 16, Telf. 3260 Zuid. T 1880 J Te huur: Gemeubileerde kamers vanaf 85 gld., '
            'zonder pension. Te bevragen: Simpang 14. T 1883 ASTROLOGIE. Vraagt Proefhoroscoop, onder '
            'opgave van plaats, dag en uur van geboorte.')
  # A rough OCR of the clipping: misreadings, line breaks, a stray mark.
  # (The last line is what Tesseract really reads in the ruled line under the ad.)
  ROUGH = 'WEGGELOOPEN\nHOND, reu, wit met bruin,\npluimstaart en lange nekharen.\nAan te geven bij :\nCoomans Emb, Kemiri 16,\nTelf. 3260 Zuid. T 1880\n|\n\nhe gem te 7 lt vn'

  def test_picks_the_clipping_in_delphers_wording(self):
    from content.transcription.match import best_part
    part, share = best_part(self.COLUMN, self.ROUGH)
    self.assertTrue(part.startswith('WEGGELOOPEN HOND, reu,'))
    self.assertTrue(part.endswith('T 1880'))                                # not the next ad's "Te huur"
    self.assertNotIn('ASTROLOGIE', part)
    self.assertGreater(share, 0.9)

  def test_nothing_to_compare(self):
    from content.transcription.match import best_part
    self.assertEqual(best_part('', 'x'), (None, 0))
    self.assertLess(best_part(self.COLUMN, 'iets heel anders dan dit')[1], 0.4)


class DelpherWithOcrTests(TestCase):
  """Delpher's text cut to the clipping by matching it with OCR of the image."""
  setUp = GuessTests.setUp
  guess = GuessTests.guess

  def test_delpher_uses_ocr_to_pick_the_clipping(self):
    Content.objects.filter(pk=self.item.pk).update(file='content/2026/clipping.jpg')
    with mock.patch('content.transcription.delpher.fetch_article', return_value=('', [MatchTests.COLUMN])), \
         mock.patch('content.transcription.tesseract.TesseractSource.available', return_value=(True, '')), \
         mock.patch('content.transcription.tesseract.read_image', return_value=MatchTests.ROUGH):
      data = self.guess(source='delpher').json()
    self.assertNotIn('ASTROLOGIE', data['text'])
    self.assertIn('matches the image', data['note'])

  def test_named_source_that_cant_says_why(self):
    Content.objects.filter(pk=self.item.pk).update(source='')
    self.assertEqual(self.guess(source='delpher').json()['error'],
                     "Delpher isn't possible here: no Delpher article link in the source.")


@skipUnless(shutil.which('tesseract'), 'tesseract is not installed (documentation/developer/installation.md)')
class TesseractReadsTests(TestCase):
  """The real thing, where Tesseract is installed: a line of Dutch text,
  rendered into an image, read back."""

  def test_reads_a_rendered_line(self):
    from django.core.files.base import ContentFile
    from PIL import Image, ImageDraw, ImageFont
    from content.transcription.tesseract import read_image
    with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
      image = Image.new('RGB', (900, 160), 'white')
      ImageDraw.Draw(image).text((30, 50), 'Lieve moeder, hier is alles goed.', fill='black', font=ImageFont.load_default(size=44))
      buffer = io.BytesIO()
      image.save(buffer, 'PNG')
      user = get_user_model().objects.create(username='ocr')
      item = Content.objects.create(name='Brief', kind='document', user=user, status='p', visibility='c')
      item.file.save('brief.png', ContentFile(buffer.getvalue()))
      text = read_image(Content.objects.get(pk=item.pk))
    self.assertIn('moeder', text.lower())


class TesseractCheckTests(TestCase):
  """content/checks.py: a missing piece of OCR is a warning at
  `manage.py check`, with a hint to documentation/developer/installation.md."""

  def ids(self):
    from content.checks import check_tesseract
    return [warning.id for warning in check_tesseract(None)]

  def test_missing_program_and_package(self):
    with mock.patch('content.checks.shutil.which', return_value=None), \
         mock.patch('content.checks.importlib.util.find_spec', return_value=None):
      self.assertEqual(self.ids(), ['content.W001', 'content.W002'])

  def test_missing_languages(self):
    with mock.patch('content.checks.shutil.which', return_value='/usr/bin/tesseract'), \
         mock.patch('content.checks.importlib.util.find_spec', return_value=object()), \
         mock.patch('pytesseract.get_languages', return_value=['eng', 'osd']):
      from content.checks import check_tesseract
      [warning] = check_tesseract(None)
    self.assertEqual(warning.id, 'content.W003')
    self.assertIn('nld', warning.msg)

  def test_all_present(self):
    from content.transcription.tesseract import LANGUAGES
    every = [name for value in LANGUAGES.values() for name in value.split('+')]
    with mock.patch('content.checks.shutil.which', return_value='/usr/bin/tesseract'), \
         mock.patch('content.checks.importlib.util.find_spec', return_value=object()), \
         mock.patch('pytesseract.get_languages', return_value=every):
      self.assertEqual(self.ids(), [])
