from django.db import models
from django.utils.translation import gettext_lazy as _


class Language(models.TextChoices):
  """The languages in this archive (ISO 639-1 codes) - for a document's
  language and a transcript's. A short list on purpose - not Django's
  ~100 UI languages, which lack Javanese and Latin and would add a
  migration whenever Django changes its list. Add one when it's needed."""
  DUTCH = 'nl', _('Dutch')
  ENGLISH = 'en', _('English')
  INDONESIAN = 'id', _('Indonesian')
  MALAY = 'ms', _('Malay')
  JAVANESE = 'jv', _('Javanese')
  GERMAN = 'de', _('German')
  FRENCH = 'fr', _('French')
  PORTUGUESE = 'pt', _('Portuguese')
  LATIN = 'la', _('Latin')
  JAPANESE = 'ja', _('Japanese')
  CHINESE = 'zh', _('Chinese')
  OTHER = 'other', _('other')
