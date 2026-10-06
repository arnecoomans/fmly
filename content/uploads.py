"""
Adding content by upload (content/new/ - one request per file, from the
dropzone; the inbox at content/inbox/).

Each file becomes a draft item of the user who uploaded it: status concept
(only they and staff see it), visibility community for once it's published,
the kind guessed from the file, named after its file when that name says
something (not IMG_1234). A file that's in the archive already (same bytes: the SHA-256
checksum) isn't added again: the answer points to the item that has it.

The date stored in a file (EXIF) is shown in the inbox as a hint, not saved:
for a scan or a phone photo of an old print it's when the copy was made, not
what it shows.
"""

import hashlib
import mimetypes

from PIL import Image

from .files import is_meaningless_filename, split_filename
from .models import Content

EXIF_DATETIME_ORIGINAL = 0x9003
EXIF_DATETIME = 0x0132
EXIF_IFD = 0x8769


def checksum_of(fileobj):
  """SHA-256 of a file's bytes, read in chunks - a 900 MB scan doesn't
  land in memory. Leaves the file at its start."""
  digest = hashlib.sha256()
  chunks = fileobj.chunks() if hasattr(fileobj, 'chunks') else iter(lambda: fileobj.read(1 << 20), b'')
  for chunk in chunks:
    digest.update(chunk)
  fileobj.seek(0)
  return digest.hexdigest()


def guess_kind(filename):
  """What an upload probably is, by its file: an image a photo, a PDF a
  document, audio or video a recording; anything else unknown. Changed in
  the inbox or on the item's page."""
  mimetype = mimetypes.guess_type(filename)[0] or ''
  if mimetype == 'application/pdf':
    return Content.Kind.DOCUMENT
  major = mimetype.split('/')[0]
  return {
    'image': Content.Kind.PHOTO, 'audio': Content.Kind.RECORDING, 'video': Content.Kind.RECORDING,
  }.get(major, Content.Kind.UNKNOWN)


def find_duplicate(checksum):
  """The item that has these bytes already, or None - any status: a
  deleted one is there too (recoverable in the admin)."""
  return Content.objects.filter(checksum=checksum).order_by('pk').first() if checksum else None


def create_upload(uploaded, user):
  """A draft item for one uploaded file - or (None, the item that has it)."""
  checksum = checksum_of(uploaded)
  duplicate = find_duplicate(checksum)
  if duplicate is not None:
    return None, duplicate
  content = Content(
    user=user, kind=guess_kind(uploaded.name), checksum=checksum,
    status=Content.Status.CONCEPT, visibility=Content.Visibility.COMMUNITY,
    # A file name that says something ("Paspoort Johan") names the item;
    # IMG_1234 and the like don't - it gets a name in the inbox.
    name='' if is_meaningless_filename(uploaded.name) else split_filename(uploaded.name)[0][:255],
  )
  content.file = uploaded
  content.save()
  return content, None


def file_date(content):
  """The date stored in an image file (EXIF: taken, else last saved), as
  'YYYY-MM-DD', or '' - a hint in the inbox, never saved. Reads the
  header only."""
  if not content.file or content.media_type != 'image':
    return ''
  try:
    with Image.open(content.file.path) as image:
      exif = image.getexif()
      value = exif.get_ifd(EXIF_IFD).get(EXIF_DATETIME_ORIGINAL) or exif.get(EXIF_DATETIME) or ''
  except (OSError, ValueError, SyntaxError):
    return ''
  value = str(value).strip()
  return value[:10].replace(':', '-') if len(value) >= 10 and value[:4].isdigit() else ''
