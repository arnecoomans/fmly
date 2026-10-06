from django.db import models
from django.utils.translation import gettext_lazy as _

from ..languages import Language


class PhotoContent(models.Model):
  class PhotoKind(models.TextChoices):
    # Posed or not first (content.forms.PhotoKindForm.choice_hints): posed,
    # one person or more; not posed, any number; the setting or the time -
    # other: not classified (yet).
    PORTRAIT = "portrait", _("portrait")
    GROUP = "group", _("group")
    CANDID = "candid", _("candid")
    HISTORICAL = "historical", _("historical")
    OTHER = "other", _("other")

  content = models.OneToOneField('content.Content', on_delete=models.CASCADE, related_name='photo_detail')
  photo_kind = models.CharField(max_length=20, choices=PhotoKind.choices, default=PhotoKind.OTHER)

  def __str__(self):
    return f"{self.content} ({self.get_photo_kind_display()})"


class DocumentContent(models.Model):
  class DocumentKind(models.TextChoices):
    CIVIL_RECORD = "civil_record", _("civil record")
    IDENTITY = "identity", _("identity document")
    SERVICE_RECORD = "service_record", _("service record")
    WAR_RECORD = "war_record", _("war record")
    NEWSPAPER = "newspaper", _("newspaper")
    ADVERTISEMENT = "advertisement", _("advertisement")
    PUBLICATION_EXCERPT = "publication_excerpt", _("publication excerpt")
    PERSONAL = "personal", _("personal paper")
    RESEARCH = "research", _("research")
    OTHER = "other", _("other")

  content = models.OneToOneField('content.Content', on_delete=models.CASCADE, related_name='document_detail')
  document_kind = models.CharField(max_length=30, choices=DocumentKind.choices, default=DocumentKind.OTHER)
  # The archive-wide list (content/languages.py), shared with Transcript.
  Language = Language

  # The language the document is written in. Blank = not set: a new
  # document isn't assumed to be anything; the legacy import sets Dutch
  # (import_content).
  language = models.CharField(max_length=10, blank=True, choices=Language.choices)

  def __str__(self):
    return f"{self.content} ({self.get_document_kind_display()})"


class BookContent(models.Model):
  """A book's own Content file is its front cover; further parts are
  Content rows with parent=<the book's Content>."""
  content = models.OneToOneField('content.Content', on_delete=models.CASCADE, related_name='book_detail')
  # Authors as people, linked by hand - an author gets a Person (family,
  # or an outsider) with their own information, so their books show on
  # their page. `author` is the plain text (legacy), shown while no one is
  # linked yet.
  authors = models.ManyToManyField('people.Person', blank=True, related_name='authored_books')
  author = models.CharField(max_length=255, blank=True, help_text=_("As written on the book; link the author as a person above"))
  publisher = models.CharField(max_length=255, blank=True)
  publication_year = models.SmallIntegerField(null=True, blank=True)
  isbn = models.CharField(max_length=20, blank=True)

  def __str__(self):
    return str(self.content)


# Content.kind -> detail model. Kinds not listed have no extra fields (yet).
DETAIL_MODELS = {
  'photo': PhotoContent,
  'document': DocumentContent,
  'book': BookContent,
}
