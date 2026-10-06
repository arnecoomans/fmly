import importlib.util
import shutil

from django.core.checks import Warning, register

INSTALL = "See documentation/developer/installation.md (Tesseract) - macOS: brew install tesseract tesseract-lang; Ubuntu: the apt line there."


@register()
def check_tesseract(app_configs, **kwargs):
  """OCR for transcripts (content/transcription/tesseract.py) needs the
  tesseract program, the pytesseract package and language data for the
  archive's languages. Warnings, not errors: without them the app works,
  and "Read the image with OCR" shows as unavailable - this makes a
  missing piece visible at `manage.py check` / start-up on a server
  instead of only as a greyed-out button."""
  warnings = []
  binary = shutil.which('tesseract')
  package = importlib.util.find_spec('pytesseract')
  if not binary:
    warnings.append(Warning(
      "The tesseract program isn't installed (or not on this process's PATH) - OCR for transcripts is unavailable.",
      hint=INSTALL, id='content.W001',
    ))
  if not package:
    warnings.append(Warning(
      "The pytesseract package isn't installed in this environment - OCR for transcripts is unavailable.",
      hint="pip install -r requirements.txt in the app's own virtualenv.", id='content.W002',
    ))
  if binary and package:
    import pytesseract
    from content.transcription.tesseract import LANGUAGES
    try:
      installed = set(pytesseract.get_languages(config=''))
    except Exception as error:  # a broken install - say so, don't crash the check
      warnings.append(Warning(f"Tesseract's languages couldn't be listed ({error}).", hint=INSTALL, id='content.W003'))
      return warnings
    wanted = {name for value in LANGUAGES.values() for name in value.split('+')}
    missing = sorted(wanted - installed)
    if missing:
      warnings.append(Warning(
        f"Tesseract has no language data for: {', '.join(missing)} - OCR in those languages falls back to Dutch, or fails.",
        hint=f"{INSTALL} (Ubuntu: tesseract-ocr-<language>, e.g. tesseract-ocr-{missing[0].replace('_', '-')}).",
        id='content.W003',
      ))
  return warnings
