"""
Content file naming - see docs/FMLY-3.0-PLAN.md, Content, "Filenames".

A file keeps the name it arrived with, unless that name is meaningless
(IMG_1234, Schermafbeelding ..., a UUID, ...): then it's named after the
content's slug, and follows the slug when the name changes. Decided on the
ORIGINAL filename, so the rule is stable: once meaningless, always
slug-named; once meaningful (e.g. NL-HaNA_2.10.50.03_418_0867s), always
kept.
"""

import os
import re

from django.conf import settings
from django.utils import timezone
from django.utils.text import get_valid_filename

# Matched case-insensitively against the filename without extension.
DEFAULT_MEANINGLESS_FILENAME_PATTERNS = [
  r'(img|dsc|dscn|dscf|pxl|mvimg|vid|mov|p)[_-]?\d+.*',  # camera / phone
  r'(schermafbeelding|screenshot|screen shot)\b.*',
  r'whatsapp (image|video|audio)\b.*',
  r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',  # UUID
  r'\d+',
  r'(image|photo|foto|scan|document|untitled|naamloos)[ _-]?\d*',
  # A scanner's own names: "Scan 2 Oct 2026 at 16.11 page 15" (Apple, also
  # "Scan 2 okt. 2026 om 16.11 pagina 15"), "Scannen0009" (and a variant
  # after it, "Scannen0018_gekleurd").
  r'scan[ _-]\d{1,2}[ _-][a-z]+\.?[ _-]\d{4}(?!\d).*',
  r'scannen\d*([ _-].*)?',
]


def _patterns():
  return getattr(settings, 'CONTENT_MEANINGLESS_FILENAME_PATTERNS', DEFAULT_MEANINGLESS_FILENAME_PATTERNS)


def split_filename(filename):
  """('Paspoort Johan', '.jpg') - basename only, extension lowercased."""
  stem, ext = os.path.splitext(os.path.basename(filename or ''))
  return stem, ext.lower()


# A leading date, as added by scanners, phones and people sorting files:
# 2023-12-10-..., 2023-12-10_..., 20231210_... It says when the FILE was
# made, not what it shows, so the name is judged on what follows it.
_DATE_PREFIX = re.compile(r'(\d{4}-\d{2}-\d{2}|\d{8})[ _-]*')


def is_meaningless_filename(filename):
  """True for a name that says nothing about the content: a camera or
  screenshot name, a UUID, just digits - also after a leading date
  (2023-12-10-IMG_1234). A date followed by real words
  (2026-09-15-Guido Gezelles dichtwerken II) is meaningful."""
  stem = split_filename(filename)[0].strip()
  stem = _DATE_PREFIX.sub('', stem, count=1) if _DATE_PREFIX.match(stem) else stem
  stem = stem.strip(' _-')
  if not stem:
    return True
  return any(re.fullmatch(pattern, stem, re.IGNORECASE) for pattern in _patterns())


def target_stem(content):
  """The stem a content's file should have: its slug if the original name
  was meaningless, otherwise the original name (made filesystem-safe)."""
  if is_meaningless_filename(content.original_filename):
    return content.slug
  return get_valid_filename(split_filename(content.original_filename)[0])


def target_directory(content):
  """content/<year the item was added> - date_created, so a new upload goes
  into this year; an item moved from FMLY 2 kept the year it was added
  there."""
  return f"content/{(content.date_created or timezone.now()).year}"


def content_upload_to(content, filename):
  """FileField upload_to: content/<year added>/<stem>.<ext>. Records the
  incoming name as original_filename, the first time only - an import or a
  re-upload of the same record doesn't overwrite what it arrived as."""
  if not content.original_filename:
    content.original_filename = os.path.basename(filename)
  stem = target_stem(content) or content.token
  return f"{target_directory(content)}/{stem}{split_filename(filename)[1]}"


def _is_named(current, directory, stem, ext):
  """current == <directory>/<stem><ext>, allowing the _abc1234 suffix
  Django's storage adds when that exact name was taken - without this, a
  suffixed file would be renamed again on every save."""
  pattern = re.escape(f"{directory}/{stem}") + r'(_[A-Za-z0-9]{7})?' + re.escape(ext)
  return bool(re.fullmatch(pattern, current))


def rename_content_file(content):
  """Move content.file to its target path - target_directory() plus
  target_stem() - if it isn't there already. Covers both a changed name
  and a file in the wrong year folder (e.g. imported before its legacy
  date_created was set). Clears sorl's cached thumbnails
  of the old name. Returns True if the file was renamed; False for no file,
  a file missing from storage, or nothing to do."""
  if not content.file:
    return False
  current = content.file.name
  directory = target_directory(content)
  ext = split_filename(current)[1]
  stem = target_stem(content) or content.token
  if _is_named(current, directory, stem, ext):
    return False

  storage = content.file.storage
  try:
    with storage.open(current, 'rb') as source:
      new_name = storage.save(f"{directory}/{stem}{ext}", source)
  except FileNotFoundError:
    return False

  from sorl.thumbnail import delete as delete_thumbnails
  delete_thumbnails(content.file, delete_file=False)
  storage.delete(current)
  type(content).objects.filter(pk=content.pk).update(file=new_name)
  content.file.name = new_name
  return True
