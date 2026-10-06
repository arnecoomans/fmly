from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class NotesConfig(AppConfig):
  name = 'notes'
  verbose_name = _("notes")
