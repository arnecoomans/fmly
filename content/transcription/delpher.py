"""
Text from Delpher (KB, the Dutch national library) for an item whose
source is a Delpher article link: the article's own OCR text through the
KB resolver - only the article identifier is sent, never the image.

Delpher counts a column of small ads as one article. When the article has
several paragraphs, the ones with the most of the search terms from the
link (?query=) are taken - likely the piece the screenshot shows. When
it's one long paragraph (the ads run together) or nothing matches, the
whole text - with a note to remove what isn't the clipping. When OCR is
available (Tesseract) and the item has its image, the clipping is picked
exactly instead: a rough OCR of the image, matched against Delpher's text
(match.py) - Delpher's wording of that part is kept, being the better OCR.
"""

import re
import xml.etree.ElementTree as ET
from urllib.error import URLError
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

from django.core.cache import cache
from django.utils.translation import gettext as _

from .base import Guess, TranscriptionError, TranscriptionSource
from .match import MIN_SHARE, best_part

RESOLVER = 'https://resolver.kb.nl/resolve?urn={urn}:ocr'
ARTICLE = re.compile(r'^[A-Za-z0-9]+:\d+:mpeg21:a\d+$')
TIMEOUT = 10
CACHE_SECONDS = 24 * 3600


def link_parts(source):
  """(article identifier, search terms, excluded terms) from a Delpher
  link - (None, [], []) when it isn't a Delpher article link."""
  url = urlparse(source or '')
  if 'delpher.nl' not in url.netloc:
    return None, [], []
  query = parse_qs(url.query)
  identifier = (query.get('identifier') or [''])[0]
  if not ARTICLE.match(identifier):
    return None, [], []
  terms, excluded = search_terms((query.get('query') or [''])[0])
  return identifier, terms, excluded


def search_terms(query):
  """'"F. coomans" AND geboorte NOT ruiter' -> (['f. coomans', 'geboorte'],
  ['ruiter']): quoted phrases and words, lowercased, operators dropped."""
  tokens = re.findall(r'"([^"]+)"|(\S+)', query or '')
  terms, excluded, negate = [], [], False
  for phrase, word in tokens:
    value = (phrase or word).strip().lower()
    if value in ('and', 'or'):
      continue
    if value == 'not':
      negate = True
      continue
    (excluded if negate else terms).append(value)
    negate = False
  return terms, excluded


def fetch_article(identifier):
  """(title, [paragraphs]) of a Delpher article - cached for a day, so the
  page's "Delpher text" and a guess don't ask twice."""
  key = f'delpher:{identifier}'
  cached = cache.get(key)
  if cached is not None:
    return cached
  request = Request(RESOLVER.format(urn=quote(identifier, safe=':')), headers={'User-Agent': 'fmly archive (transcription)'})
  try:
    with urlopen(request, timeout=TIMEOUT) as response:
      body = response.read()
  except (URLError, TimeoutError, OSError) as error:
    raise TranscriptionError(_("Delpher didn't answer (%(error)s).") % {'error': error}) from error
  try:
    root = ET.fromstring(body)
  except ET.ParseError as error:
    raise TranscriptionError(_("Delpher's answer couldn't be read.")) from error
  title = ' '.join((root.findtext('title') or '').split())
  paragraphs = [' '.join(''.join(p.itertext()).split()) for p in root.iter('p')]
  article = (title, [p for p in paragraphs if p])
  cache.set(key, article, CACHE_SECONDS)
  return article


# A single paragraph longer than this probably holds more than one piece
# (a column of ads run together).
LONG = 500


def select(paragraphs, terms, excluded):
  """The paragraphs to keep: all of one; else those with the most distinct
  search terms (and none of the excluded ones) - a term that happens to
  occur in a neighbouring ad doesn't pull it in; all when nothing
  matches."""
  if len(paragraphs) <= 1 or not terms:
    return paragraphs
  def score(paragraph):
    text = paragraph.lower()
    if any(term in text for term in excluded):
      return 0
    return sum(1 for term in terms if term in text)
  scores = [score(p) for p in paragraphs]
  best = max(scores)
  return [p for p, s in zip(paragraphs, scores) if best and s == best] or paragraphs


class DelpherSource(TranscriptionSource):
  name = 'delpher'
  label = _("Fetch text from Delpher")
  short = _("Delpher")
  icon = 'cloud-download'
  explanation = _("The article's own text from the KB - only the article number from the source link is sent.")

  def applies(self, content):
    identifier, _terms, _excluded = link_parts(content.source)
    return (True, '') if identifier else (False, _("no Delpher article link in the source"))

  def guess(self, content):
    identifier, terms, excluded = link_parts(content.source)
    title, paragraphs = fetch_article(identifier)
    if not paragraphs and not title:
      return None
    matched = self._match_image(content, title, paragraphs)
    if matched:
      return matched
    chosen = select(paragraphs, terms, excluded)
    text = '\n\n'.join(([title] if title and len(chosen) == len(paragraphs) else []) + chosen)
    note = _("From Delpher - check it: their OCR may contain errors, and the end can belong to the next piece.")
    if len(chosen) == 1 and len(chosen[0]) > LONG:
      note = _("From Delpher - this article holds more than your clipping probably shows: remove what isn't yours, and check the rest.")
    elif len(chosen) < len(paragraphs):
      note = _("From Delpher: %(n)s of %(total)s pieces of the article (those with your search terms) - check it.") % {
        'n': len(chosen), 'total': len(paragraphs)}
    return Guess(text=text, language='nl', note=note)

  def _match_image(self, content, title, paragraphs):
    """The part of the article the image shows, when OCR can read the image
    - also for a short article: it trims what belongs to the next piece
    (a byline, the next heading). None when it can't, or the match is too
    weak - then the article's text as chosen by the search terms."""
    from .tesseract import TesseractSource, read_image
    whole = '\n'.join([title, *paragraphs]) if title else '\n'.join(paragraphs)
    ocr = TesseractSource()
    if not (ocr.applies(content)[0] and ocr.available()[0]):
      return None
    try:
      rough = read_image(content, 'nl')
    except TranscriptionError:
      return None
    part, share = best_part(whole, rough)
    if not part or share < MIN_SHARE:
      return None
    return Guess(
      text=part, language='nl',
      note=_("From Delpher: the part of the article that matches the image (found by comparing it with OCR of the image) - check the beginning and end."),
    )
