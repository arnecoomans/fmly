from django.apps import AppConfig
from django.conf import settings


class ContentConfig(AppConfig):
  name = 'content'

  def ready(self):
    from content import checks  # noqa: F401 - registers system checks (Tesseract for OCR)
    # Pillow refuses images over ~179 megapixels ("decompression bomb"
    # guard, against crafted uploads meant to exhaust memory). The archive
    # holds genuine scans of old photos up to ~260 MP, uploaded by signed-
    # in family members - so the limit is raised, not removed, to
    # CONTENT_MAX_IMAGE_PIXELS. Decoding stays cheap for thumbnails:
    # content.thumbnail_engine reads JPEGs in draft mode.
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = getattr(settings, 'CONTENT_MAX_IMAGE_PIXELS', 300_000_000)
    # HEIC/HEIF (iPhone photos): Pillow reads them through pillow-heif, so
    # thumbnails, the large view and the dimensions work - all rendered as
    # JPEG. The file itself stays HEIC (only Safari shows that directly; the
    # lightbox zooms into a JPEG rendering instead - Content.zoom_url).
    try:
      from pillow_heif import register_heif_opener
    except ImportError:
      pass
    else:
      register_heif_opener()
