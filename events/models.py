from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from datetime import date

from cmnsd.models.access import filter_accessible
from cmnsd.models.mixins import TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin, PartialDateMixin, EditableRelationsMixin
from core.models import CommentableMixin

from cmnsd.api.registry import api_model, api_field


class EventQuerySet(models.QuerySet):
  def current(self):
    """Not deleted - for code that reads events directly instead of through
    filter_accessible (a person's birth and death, lifespans): a deleted
    event is gone for everyone."""
    return self.exclude(status=StatusMixin.Status.DELETED)


# In the API for the event picker (edit mode); visibility derived from the
# people (filter_visibility below), search via api_search_q.
@api_model(search_fields=['title', 'kind_freetext', 'description'])
class Event(TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin, PartialDateMixin, EditableRelationsMixin,
            CommentableMixin, models.Model):
  class Kind(models.TextChoices):
    BIRTH = "birth", _("birth")
    DEATH = "death", _("death")
    MARRIAGE = "marriage", _("marriage")
    MIGRATION = "migration", _("migration")
    HISTORICAL = "historical", _("historical")   # history, often without people (the Japanese invasion)
    OTHER = "other", _("other")

  # Published from the start, like people (the site's default status is
  # concept); deleting is a status (StatusMixin): hidden from everyone,
  # recoverable in the admin.
  status = models.CharField(max_length=1, choices=StatusMixin.Status.choices, default=StatusMixin.Status.PUBLISHED)

  kind = api_field(readonly=True)(
    models.CharField(max_length=20, choices=Kind.choices)
  )
  kind_freetext = models.CharField(
    max_length=255, blank=True,
    help_text=_("Custom label for this event - required when kind is 'other'"),
  )
  title = models.CharField(max_length=255, blank=True)
  description = models.TextField(blank=True)

  # blank=True: a historical event (opening of the Suez Canal) has
  # no people at all; birth/death/marriage populate this.
  # Cardinality (birth/death: exactly 1 person, marriage: 2+) is NOT
  # enforced here - clean()/save() run via full_clean() before the row has
  # a pk, and M2M fields can't be read until then. Enforce this in the
  # add/edit Event form's clean() once it exists, not on the model.
  people = models.ManyToManyField('people.Person', blank=True, related_name='events')

  # Most events have one place; some need more (migration: from and to,
  # a treaty signed across two countries) - plain M2M, no from/to ordering.
  places = models.ManyToManyField('places.Place', blank=True, related_name='events')

  objects = EventQuerySet.as_manager()
  # Dismissed from a loose end ("fine as it is", dashboard.LooseEndDismissal):
  # the rows go with the item.
  loose_end_dismissals = GenericRelation('dashboard.LooseEndDismissal')

  # Edit mode on the event's page (cmnsd object_form): block -> form (dotted:
  # events/forms.py imports this model); the page shows
  # event/blocks/<block>.html.
  api_edit_forms = {
    'what': 'events.forms.EventWhatForm',
    'date': 'events.forms.EventDateForm',
    'description': 'events.forms.EventDescriptionForm',
    'status': 'events.forms.EventStatusForm',
  }
  # Edit mode: who, where, and the items documenting it (EditableRelationsMixin).
  # `content` is Content.events seen from the event. Places may be created
  # by name; people have more fields - their picker offers "+ new person".
  api_editable_relations = {
    'people': {},
    'places': {'create': {}},
    'content': {},
  }
  # A new event in a dialog (cmnsd object_create): the events page's
  # "+ New event", a timeline's "+ add an event", the event pickers.
  api_create_form = 'events.forms.EventCreateForm'

  # Comments (CommentableMixin): the relation, the thread, add_comment.

  class Meta:
    ordering = ['year', 'month', 'day']
    indexes = [
      models.Index(fields=['kind', 'year']),
    ]

  def get_absolute_url(self):
    """events/<token>/ - no slug: an event's name depends on who's looking
    (display_for)."""
    from django.urls import reverse
    return reverse('events:detail', kwargs={'token': self.token})

  def get_list_url(self):
    from django.urls import reverse
    return reverse('events:list')

  def label(self):
    """What it is, in a word or a title: its own title, else its own label
    (an 'other' event), else its kind - 'Inval Japan Nederlands Indië',
    'Verhuizing naar Medan', 'Marriage'."""
    return self.title or (self.kind_freetext[:1].upper() + self.kind_freetext[1:]) or self.get_kind_display().capitalize()

  def __str__(self):
    """Every person by name - for the admin and logs only. Anything a
    viewer sees uses display_for(user): an event names its people, and not
    every viewer may see every person."""
    return self._title([p.get_full_name() for p in self.people.all()])

  def _title(self, names):
    title = self.title or self.kind_freetext or self.get_kind_display()
    if names:
      title += f" of { ', '.join(names) }"
    places = [p.name for p in self.places.all()]
    if places:
      title += f" @ { ', '.join(places) }"
    if self.year:
      title += f" ({ self.year })"
    return title

  def display_for(self, user=None):
    """The event's name as `user` may see it: the people they may see by
    name, the others obfuscated (initials only - core.templatetags.
    visibility.obfuscate_name, as on a person's own rows)."""
    from core.templatetags.visibility import obfuscate_name
    names = [
      p.get_full_name() if self._person_visible(p, user) else obfuscate_name(p.get_full_name())
      for p in self.people.all()
    ]
    return self._title(names)

  def api_display(self, request):
    """What the API shows as this event's name (cmnsd object_list)."""
    return self.display_for(getattr(request, 'user', None))

  @api_field(readonly=True)
  def summary(self, request=None):
    return self.display_for(getattr(request, 'user', None))

  # --- Visibility: derived from the people (no field of its own) ----------
  # An event is visible when at least one of its people is visible to the
  # viewer (status + visibility); an event without people - a general,
  # historical event - is visible to everyone. Its hidden people are shown
  # obfuscated (display_for). Duck-typed for cmnsd: filter_accessible() and
  # the API apply filter_visibility(); is_visible_to() is the same rule for
  # one loaded event.

  @staticmethod
  def _person_visible(person, user):
    return person.is_status_visible_to(user) and person.is_visible_to(user)

  @classmethod
  def filter_visibility(cls, queryset, request=None):
    from people.models import Person
    visible = filter_accessible(Person.objects.all(), request)
    return queryset.filter(Q(people__in=visible) | Q(people__isnull=True)).distinct()

  def is_visible_to(self, user=None):
    people = list(self.people.all())
    return not people or any(self._person_visible(p, user) for p in people)

  @classmethod
  def api_search_q(cls, term, request=None):
    """Extra free-text search for the API (cmnsd.api.filtering): the names
    of the people the viewer may see - never the hidden ones, so a search
    can't tell whether a hidden person is in an event - plus place names
    and the year."""
    from people.models import Person
    named = filter_accessible(Person.objects.all(), request).filter(
      Q(given_name__icontains=term) | Q(called_name__icontains=term) | Q(last_name__icontains=term)
      | Q(married_name__icontains=term) | Q(nickname__icontains=term)
    )
    q = Q(people__in=named) | Q(places__name__icontains=term)
    if term.isdigit():
      q |= Q(year=int(term))
    return q
  
  def clean(self):
    super().clean()   # the partial date's rules (PartialDateMixin)
    if self.kind == self.Kind.OTHER and not self.kind_freetext:
      raise ValidationError({
        'kind_freetext': _("Provide a freetext label when kind is 'other'."),
      })

  def save(self, *args, **kwargs):
    self.full_clean()
    super().save(*args, **kwargs)

  def calendar_date(self):
    """Return a datetime.date object for this event's year/month/day, or None
    if any of those are missing - or the date isn't exact: a weekday for
    "ca. 6-1-1943" would claim a precision nobody has. Useful for calendar
    display."""
    if self.year and self.month and self.day and self.is_exact_date():
      partial_date = date(self.year, self.month, self.day)
      return partial_date
    return None
