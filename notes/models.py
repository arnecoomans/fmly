from django.db import models
from django.urls import reverse
from django.utils.text import Truncator
from django.utils.translation import gettext_lazy as _

from cmnsd.api.registry import api_field, api_model
from cmnsd.models.access import filter_accessible
from cmnsd.models.mixins import (
  TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin, VisibilityMixin, PartialDateMixin,
  EditableRelationsMixin,
)


class NoteQuerySet(models.QuerySet):
  def visible_to(self, request):
    """What this viewer may see: status, then visibility (cmnsd
    filter_accessible) - a draft only for its author, a private note only
    for its author."""
    return filter_accessible(self, request)

  def in_order(self):
    """Open work first - to do, questions, hypotheses - then the settled
    and background notes; within a kind the most recently changed first."""
    order = models.Case(
      *[models.When(kind=kind, then=index) for index, kind in enumerate(Note.KIND_ORDER)],
      default=len(Note.KIND_ORDER), output_field=models.IntegerField(),
    )
    return self.order_by(order, '-date_modified')


# In the API: the picker for "links to another note" (GET api/note/?q=...&
# format=picker), the list filter ?kind=, and the edit-mode blocks.
@api_model(search_fields=['title', 'body'])
class Note(TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin, VisibilityMixin, PartialDateMixin,
           EditableRelationsMixin, models.Model):
  """Research material: a lead, a question, a hypothesis, a conclusion,
  background - one model, told apart by `kind`, so a question can become
  a conclusion without moving rows (docs/NOTES.md). The glue between
  content, people, places and events: a note links to any of them, and to
  other notes.

  Dated facts stay in Event: a note links to events (a conclusion cites or
  leads to one) rather than being one. Not every note needs links - scratch
  and to-do notes are raw material.

  A note starts as a draft that only its author sees (status concept,
  visibility private); publishing and sharing are explicit, as for content."""

  class Kind(models.TextChoices):
    SCRATCH = 'scratch', _("scratch")
    TODO = 'todo', _("to do")
    QUESTION = 'question', _("question")
    HYPOTHESIS = 'hypothesis', _("hypothesis")
    CONCLUSION = 'conclusion', _("conclusion")
    CONTEXT = 'context', _("context")

  # Open work first (the notes list, NoteQuerySet.in_order).
  KIND_ORDER = (Kind.TODO, Kind.QUESTION, Kind.HYPOTHESIS, Kind.CONCLUSION, Kind.CONTEXT, Kind.SCRATCH)

  class Confidence(models.TextChoices):
    CERTAIN = 'certain', _("certain")
    PROBABLE = 'probable', _("probable")
    UNCERTAIN = 'uncertain', _("uncertain")

  kind = api_field(readonly=True)(
    models.CharField(max_length=20, choices=Kind.choices, default=Kind.SCRATCH)
  )
  title = models.CharField(max_length=255, blank=True)
  body = models.TextField(blank=True, help_text=_("The reasoning, a quoted source, the anecdote - Markdown"))
  confidence = models.CharField(max_length=20, choices=Confidence.choices, blank=True)

  # A new note is a private draft (StatusMixin / VisibilityMixin default
  # to published and community).
  status = models.CharField(max_length=1, choices=StatusMixin.Status.choices, default=StatusMixin.Status.CONCEPT)
  visibility = models.CharField(max_length=1, choices=VisibilityMixin.Visibility.choices, default=VisibilityMixin.Visibility.PRIVATE)

  people = models.ManyToManyField('people.Person', blank=True, related_name='notes')
  content = models.ManyToManyField('content.Content', blank=True, related_name='notes')
  places = models.ManyToManyField('places.Place', blank=True, related_name='notes')
  events = models.ManyToManyField('events.Event', blank=True, related_name='notes')
  tags = models.ManyToManyField('core.Tag', blank=True, related_name='notes')
  # One way: this note refers to those ("links to"); they show this one
  # as "linked from".
  related_notes = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='linked_from')

  objects = NoteQuerySet.as_manager()

  # Edit mode (cmnsd object_form): block -> form (dotted: notes/forms.py
  # imports this model). The page shows note/blocks/<block>.html.
  api_edit_forms = {
    'title': 'notes.forms.NoteTitleForm',
    'body': 'notes.forms.NoteBodyForm',
    'date': 'notes.forms.NoteDateForm',
    'kind': 'notes.forms.NoteKindForm',
    'confidence': 'notes.forms.NoteConfidenceForm',
    'visibility': 'notes.forms.NoteVisibilityForm',
    'status': 'notes.forms.NoteStatusForm',
  }

  # Edit mode: link and unlink (EditableRelationsMixin). Tags and places may
  # be created by name; people and events have more fields - the picker
  # links to their add page.
  api_editable_relations = {
    'people': {},
    'content': {},
    'places': {'create': {}},
    'events': {},
    'tags': {'create': {'status': 'p', 'visibility': 'c'}},
    'related_notes': {},
  }

  class Meta:
    ordering = ['-date_modified']
    verbose_name = _("note")
    verbose_name_plural = _("notes")

  def __str__(self):
    if self.title:
      return self.title
    first_line = (self.body or '').strip().split('\n', 1)[0].lstrip('#* ').strip()
    return Truncator(first_line).chars(60) if first_line else str(_("untitled note"))

  def get_absolute_url(self):
    """notes/<token>/ - no slug: a title is optional and changes as the
    research does."""
    return reverse('notes:detail', kwargs={'token': self.token})

  def get_list_url(self):
    return reverse('notes:list')

  @property
  def is_open(self):
    """Work still to do: a to-do or an unanswered question."""
    return self.kind in (self.Kind.TODO, self.Kind.QUESTION)
