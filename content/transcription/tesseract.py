"""
OCR with Tesseract, on this server - nothing leaves it (docs/issues.md,
the OCR plan, step 2; installation: documentation/developer/installation.md). Available once the
tesseract program and the pytesseract package are installed; until then
the option shows, disabled.

The image is read upright (EXIF), in grayscale, at a size Tesseract reads
well - a small scan enlarged, a huge one reduced - with automatic page
layout (columns, reading order), in the document's language.
"""

import importlib.util
import re
import shutil

from django.utils.translation import gettext as _

from .base import Guess, TranscriptionError, TranscriptionSource

# The archive's languages (content/languages.py) as Tesseract names them.
LANGUAGES = {
  'nl': 'nld', 'en': 'eng', 'id': 'ind', 'ms': 'msa', 'jv': 'jav', 'de': 'deu',
  'fr': 'fra', 'pt': 'por', 'la': 'lat', 'ja': 'jpn', 'zh': 'chi_sim+chi_tra',
}
DEFAULT_LANGUAGE = 'nl'   # the archive's own
SMALL, LARGE = 1600, 4000  # longest side, in pixels: enlarge below, reduce above
MAX_ENLARGE = 3
TIMEOUT = 90              # seconds - a page, not a book


def document_language(content):
  """The item's language as an archive code: a document's own, else Dutch."""
  detail = getattr(content, 'document_detail', None) if content.kind == 'document' else None
  return getattr(detail, 'language', '') or DEFAULT_LANGUAGE


def _tesseract_language(code):
  import pytesseract
  wanted = LANGUAGES.get(code, LANGUAGES[DEFAULT_LANGUAGE])
  installed = set(pytesseract.get_languages(config=''))
  parts = [part for part in wanted.split('+') if part in installed]
  if parts:
    return '+'.join(parts)
  if 'nld' in installed:
    return 'nld'
  raise TranscriptionError(_("The language data for this text isn't installed (see documentation/developer/installation.md)."))


def _prepared(content):
  """The item's image, ready for Tesseract: upright, grayscale, sized."""
  from PIL import Image, ImageOps
  try:
    with content.file.open('rb') as handle:
      image = Image.open(handle)
      image.load()
  except (OSError, ValueError) as error:
    raise TranscriptionError(_("The image couldn't be opened.")) from error
  image = ImageOps.exif_transpose(image).convert('L')
  longest = max(image.size)
  if longest < SMALL:
    factor = min(MAX_ENLARGE, SMALL / longest)
  elif longest > LARGE:
    factor = LARGE / longest
  else:
    factor = 1
  if factor != 1:
    image = image.resize((round(image.width * factor), round(image.height * factor)), Image.LANCZOS)
  return image


def tidy(text):
  """Trailing spaces off each line, at most one empty line in a row."""
  lines = [line.rstrip() for line in (text or '').splitlines()]
  return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def read_image(content, language=None):
  """The text Tesseract reads in the item's image."""
  import pytesseract
  lang = _tesseract_language(language or document_language(content))
  try:
    text = pytesseract.image_to_string(_prepared(content), lang=lang, config='--psm 3', timeout=TIMEOUT)
  except RuntimeError as error:   # pytesseract's timeout
    raise TranscriptionError(_("Reading the image took too long.")) from error
  except pytesseract.TesseractError as error:
    raise TranscriptionError(_("Tesseract couldn't read the image (%(error)s).") % {'error': error}) from error
  return tidy(text)


class TesseractSource(TranscriptionSource):
  name = 'tesseract'
  label = _("Read the image with OCR")
  short = _("OCR")
  icon = 'fonts'
  explanation = _("Tesseract, on this server - the image doesn't leave it.")

  def applies(self, content):
    if content.file and content.media_type == 'image':
      return True, ''
    return False, _("no image to read")

  def available(self):
    if shutil.which('tesseract') and importlib.util.find_spec('pytesseract'):
      return True, ''
    return False, _("not installed on this server")

  def guess(self, content):
    language = document_language(content)
    text = read_image(content, language)
    if not text:
      return None
    return Guess(
      text=text, language=language,
      note=_("Read by OCR (Tesseract) - check it carefully: it misreads old print and handwriting."),
    )
