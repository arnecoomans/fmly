from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from cmnsd.models import MentionableSourceMixin
from cmnsd.models.mixins import TimestampMixin

from ..languages import Language


class Transcript(MentionableSourceMixin, TimestampMixin, models.Model):
  """What is literally written on an item (the original), or a
  translation of that - separate from the description, which says what
  the item is. Any kind of content: documents, but also a photo's back or
  a book excerpt. At most one transcript per language per item, and at
  most one original.

  method: typed by hand, or automatic - OCR for an original, machine
  translation (e.g. Google Lens) for a translation - unchecked or checked
  by someone. Automatic output never replaces a manual or checked
  transcript (save_automatic)."""

  class Kind(models.TextChoices):
    ORIGINAL = 'original', _('original')
    TRANSLATION = 'translation', _('translation')

  class Method(models.TextChoices):
    MANUAL = 'manual', _('manual')
    AUTOMATIC = 'automatic', _('automatic, not checked')
    AUTOMATIC_CHECKED = 'automatic_checked', _('automatic, checked')

  content = models.ForeignKey('content.Content', on_delete=models.CASCADE, related_name='transcripts')
  kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.ORIGINAL)
  language = models.CharField(max_length=10, choices=Language.choices)
  method = models.CharField(max_length=20, choices=Method.choices, default=Method.MANUAL)
  text = models.TextField()
  # Its mentions indexed on save (cmnsd.models.Mention, issue #474):
  # "mentioned in the transcript of ...".
  mention_fields = ('text',)

  def mention_reach_of(self):
    """Who reads this transcript: who may see its item (cmnsd reaches_fewer)."""
    return self.content

  def mention_excluded_targets(self):
    """What this transcript mentioning doesn't count as "mentioned in"
    (cmnsd sync_mentions): its own item - the whole and its parts, a page
    of a book naming the book - it's that item's own text."""
    from .Content import Content
    whole_id = self.content.parent_id or self.content_id
    pks = {whole_id, self.content_id, *Content.objects.filter(parent_id=whole_id).values_list('pk', flat=True)}
    return [(Content, pks)]

  @classmethod
  def mention_sources_for(cls, queryset, request):
    """The transcripts among these this viewer may read as "mentioned in":
    as visible as their item (a transcript has no visibility of its own).
    One per item - the original before a translation - so an item that
    names someone in two languages is listed once."""
    from .Content import Content
    visible = queryset.filter(content__in=Content.objects.visible_to(request)).order_by('content_id', 'pk')
    first = {}
    for transcript in visible:
      kept = first.get(transcript.content_id)
      if kept is None or (kept.kind != cls.Kind.ORIGINAL and transcript.kind == cls.Kind.ORIGINAL):
        first[transcript.content_id] = transcript
    return list(first.values())
  # Not all of it typed yet - an honest marker for a partial transcript
  # (off by default: the aim is a full one).
  incomplete = models.BooleanField(default=False, help_text=_("Only part of the text is transcribed so far"))

  class Meta:
    # Original first, then translations by language.
    ordering = ['kind', 'language']  # 'original' < 'translation'
    constraints = [
      models.UniqueConstraint(
        fields=['content', 'language'], name='content_transcript_one_per_language',
        violation_error_message=_("This item already has a transcript in that language."),
      ),
      models.UniqueConstraint(
        fields=['content'], condition=Q(kind='original'), name='content_transcript_one_original',
        violation_error_message=_("This item already has an original - add this as a translation."),
      ),
    ]

  def __str__(self):
    return f"{self.content} - {self.get_language_display()} ({self.get_kind_display()})"

  @property
  def is_unchecked(self):
    return self.method == self.Method.AUTOMATIC

  def clean(self):
    if not (self.text or '').strip():
      raise ValidationError({'text': _("A transcript can't be empty.")})

  @classmethod
  def save_automatic(cls, content, language, text, kind=Kind.ORIGINAL):
    """Store OCR / machine-translation output as 'automatic, not checked'
    - unless this item already has a manual or checked transcript in that
    language, which is never overwritten. Returns the transcript, or None
    when it was left alone."""
    existing = cls.objects.filter(content=content, language=language).first()
    if existing and existing.method != cls.Method.AUTOMATIC:
      return None
    transcript = existing or cls(content=content, language=language)
    transcript.kind, transcript.text, transcript.method = kind, text, cls.Method.AUTOMATIC
    transcript.full_clean()
    transcript.save()
    return transcript
