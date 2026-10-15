"""
A preview image of a file that isn't an image itself - a PDF's first page -
so it gets a thumbnail like a photo: an image card in the grids, the
dashboard's thumbnails, a crop of its own (content.views.files
content_thumbnail). Derived from the file, never entered by hand: always
right, nothing to keep up to date (documentation/developer/architecture.md,
Design principles).

One image per file, rendered once at PREVIEW_SIZE and kept in the cache
next to the thumbnails (private/cache/previews/, as protected as the
originals); every thumbnail size is made from it by sorl. The name has the
file's checksum in it: a replaced PDF gets a new preview, the old one is
left for the cache to be cleared.

pypdfium2 (Chrome's PDF engine): page 1 only, and PDFium loads lazily - a
550-page scanned book renders its first page in a few hundredths of a
second, in little memory.
"""

import io
import logging

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

logger = logging.getLogger(__name__)

PREVIEW_SIZE = 1600   # px, the longer side - enough for the 'large' preset
PREVIEW_DIR = 'cache/previews'


def has_preview(content):
  """Whether this item's file gets a generated preview: a PDF."""
  return bool(content.file) and content.media_type == 'pdf'


def preview_name(content):
  """The preview's name in the default storage (MEDIA_ROOT = private/)."""
  version = (content.checksum or '')[:12] or 'nochecksum'
  return f'{PREVIEW_DIR}/{content.token}-{version}.jpg'


def ensure_preview(content):
  """The preview's storage name - rendered first if it isn't there yet - or
  None when this file has none or can't be read (encrypted, damaged)."""
  if not has_preview(content):
    return None
  name = preview_name(content)
  if default_storage.exists(name):
    return name
  try:
    image = _render_first_page(content.file.path)
  except Exception:   # pypdfium2 raises its own PdfiumError, among others
    logger.warning("No preview for %s: its PDF can't be rendered.", content.token, exc_info=True)
    return None
  buffer = io.BytesIO()
  image.save(buffer, 'JPEG', quality=85, optimize=True)
  return default_storage.save(name, ContentFile(buffer.getvalue()))


def _render_first_page(path):
  import pypdfium2 as pdfium
  pdf = pdfium.PdfDocument(path)
  try:
    page = pdf[0]
    width, height = page.get_size()   # in points
    scale = min(PREVIEW_SIZE / width, PREVIEW_SIZE / height)
    return page.render(scale=scale).to_pil().convert('RGB')
  finally:
    pdf.close()
