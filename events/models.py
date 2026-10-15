from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from datetime import date

from cmnsd.models.access import filter_accessible
from cmnsd.models.search import contains
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
# people (filter_visibility below), search via api_search_q. Not the
# description here: it's for signed-in viewers only (api_search_q).
@api_model(search_fields=['title'])
class Event(TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin, PartialDateMixin, EditableRelationsMixin,
            CommentableMixin, models.Model):
  class Kind(models.TextChoices):
    BIRTH = "birth", _("birth")
    DEATH = "death", _("death")
    MARRIAGE = "marriage", _("marriage")
    DIVORCE = "divorce", _("divorce")       # explains a timeline: why a partner is gone while alive
    MIGRATION = "migration", _("migration")
    # Proof someone lived somewhere, without knowing when they moved there -
    # evidence that isn't an item in the archive (an address book, a
    # population register; the source in the description). GEDCOM RESI.
    # A person's own event like any other (issue #465).
    RESIDENCE = "residence", _("residence")
    HISTORICAL = "historical", _("historical")   # history, often without people (the Japanese invasion)
    OTHER = "other", _("other")

  # Kinds that name themselves ("Marriage", with its people): no title -
  # the forms hide the field, clean() clears it (events/forms.py).
  UNTITLED_KINDS = (Kind.BIRTH, Kind.DEATH, Kind.MARRIAGE, Kind.DIVORCE)

  # Published from the start, like people (the site's default status is
  # concept); deleting is a status (StatusMixin): hidden from everyone,
  # recoverable in the admin.
  status = models.CharField(max_length=1, choices=StatusMixin.Status.choices, default=StatusMixin.Status.PUBLISHED)

  kind = api_field(readonly=True)(
    models.CharField(max_length=20, choices=Kind.choices)
  )
  title = models.CharField(max_length=255, blank=True)
  description = models.TextField(blank=True)

  # blank=True: a historical event (opening of the Suez Canal) has
  # no people at all; birth/death/marriage/divorce populate this.
  # Cardinality (birth/death: exactly 1 person, marriage/divorce: 2+) is NOT
  # enforced here - clean()/save() run via full_clean() before the row has
  # a pk, and M2M fields can't be read until then. Enforce this in the
  # add/edit Event form's clean() once it exists, not on the model.
  people = models.ManyToManyField('people.Person', blank=True, related_name='events')

  # Most events have one place; some need more (migration: from and to,
  # a treaty signed across two countries) - plain M2M, no from/to ordering.
  places = models.ManyToManyField('places.Place', blank=True, related_name='events')

  # Background (issue #464): this event made those possible, or explains
  # them - "Sibajak released for repatriation" is background for "Arrival
  # per Sibajak". One way: the people of those events see this one on
  # their timeline as background, not the other way around
  # (people/timeline.py); one step, it doesn't carry on. A historical event
  # that's background for an event *with people* is specific context, no
  # longer general history for everyone alive at the time - background for
  # an event without people changes nothing on a timeline (Hiroshima for
  # the surrender of Japan would otherwise vanish from all of them).
  # event.background: the reverse - what explains this event. Edited from
  # that side, on an event with people (api_editable_relations).
  background_for = models.ManyToManyField(
    'self', symmetrical=False, blank=True, related_name='background',
    help_text=_("Events this one is background for: what made them possible, or explains them"),
  )

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
    # What explains this event (Event.background_for seen from here) - only
    # for an event with people, never itself: _related refuses both.
    'background': {},
  }
  def _related(self, manager, request, token):
    """EditableRelationsMixin: the object to link. For `background` (the
    only relation to events): never this event itself, and only when this
    event has people - background is for the people in it (people/
    timeline.py). Refused before anything is added (see
    not_its_own_background below)."""
    obj = super()._related(manager, request, token)
    if isinstance(obj, Event):
      if obj == self:
        raise ValidationError(_("An event can't be background for itself."))
      if not self.people.exists():
        raise ValidationError(_("Background is for the people in an event - add them first."))
    return obj

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
    """What it is, in a word or a title: its title, else its kind - 'Inval
    Japan Nederlands Indië', 'Verhuizing naar Medan', 'Marriage'."""
    return (self.title[:1].upper() + self.title[1:]) or self.get_kind_display().capitalize()

  def __str__(self):
    """Every person by name - for the admin and logs only. Anything a
    viewer sees uses display_for(user): an event names its people, and not
    every viewer may see every person."""
    return self._title([p.get_full_name() for p in self.people.all()])

  def _title(self, names):
    title = self.title or self.get_kind_display()
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
    and the year; the description only for someone signed in. An event is
    visible through its people, but its description may say more than
    they do (a cause of death, a family matter): signed out, it's neither
    shown (event/_event.html, blocks/description.html) nor searched - a
    match would give its words away."""
    from people.models import Person
    named = filter_accessible(Person.objects.all(), request).filter(
      Q(**{contains('given_name'): term}) | Q(**{contains('called_name'): term}) | Q(**{contains('last_name'): term})
      | Q(**{contains('married_name'): term}) | Q(**{contains('nickname'): term})
    )
    q = Q(people__in=named) | Q(**{contains('places__name'): term})
    if request is not None and request.user.is_authenticated:
      q |= Q(**{contains('description'): term})
    if term.isdigit():
      q |= Q(year=int(term))
    return q
  
  def clean(self):
    super().clean()   # the partial date's rules (PartialDateMixin)
    # The four fixed kinds name themselves: a title there is a leftover from
    # another kind (the forms hide it for them).
    if self.kind in self.UNTITLED_KINDS:
      self.title = ''
    if self.kind == self.Kind.OTHER and not self.title:
      raise ValidationError({
        'title': _("Say what it was - required for kind 'other'."),
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


@receiver(m2m_changed, sender=Event.background_for.through)
def not_its_own_background(sender, instance, action, pk_set, **kwargs):
  """An event is never background for itself - from either side of the
  relation, whoever adds it (the admin, a script): dropped quietly. Not
  raised: add() runs in an atomic block without a savepoint, so an error
  here would break the whole surrounding transaction. The link action
  refuses it with a message first (Event._related)."""
  if action == 'pre_add' and pk_set:
    pk_set.discard(instance.pk)
