"""
Ways to get a first version of a transcription, each a plainly named
button on the transcribe page ("Fetch text from Delpher", "Read the image
with OCR") - no hidden default: what you click is what happens. Each says
whether it applies to the item and is available on this server (a
disabled button says why). The result is a starting point, saved as
"automatic, not checked" for someone to correct.
"""

from django.utils.translation import gettext as _

from .base import Guess, TranscriptionError
from .delpher import DelpherSource
from .tesseract import TesseractSource

SOURCES = [DelpherSource(), TesseractSource()]


def options(content):
  """[{name, label, enabled, reason}] - every source, for the menu; a
  disabled one says why (doesn't apply to this item / not installed)."""
  result = []
  for source in SOURCES:
    applies, why_not = source.applies(content)
    available, why_unavailable = source.available()
    result.append({
      'name': source.name, 'label': source.label, 'icon': source.icon, 'explanation': source.explanation,
      'enabled': applies and available, 'reason': '' if applies and available else (why_not or why_unavailable),
    })
  return result


def guess(content, name=None):
  """A Guess from source `name`, or from the first usable one. Raises
  TranscriptionError when none can (or the chosen one can't)."""
  for source in SOURCES:
    if name and source.name != name:
      continue
    if source.applies(content)[0] and source.available()[0]:
      result = source.guess(content)
      if result and result.text.strip():
        return source, result
      if name:
        raise TranscriptionError(_("%(source)s found no text.") % {'source': source.short})
    elif name:
      reason = source.applies(content)[1] or source.available()[1]
      raise TranscriptionError(_("%(source)s isn't possible here: %(reason)s.") % {'source': source.short, 'reason': reason})
  raise TranscriptionError(_("No source could provide a text."))


__all__ = ['Guess', 'TranscriptionError', 'SOURCES', 'options', 'guess']
