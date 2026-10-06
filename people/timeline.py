"""
A person's life as a timeline (the Events section of their page): their own
events - birth, marriages, migrations, death, ... - those of their close
family that fall within their life: children's births and deaths, parents'
and partners' deaths - and the history around it: historical events without
people (the Japanese invasion, the transfer of sovereignty) dated within
their life. Each entry knows the person's age at it, when both
dates are known.

Only what this viewer may see: an event by its visibility (through its
people), a relative only when visible - a hidden child's birth doesn't show
up in a parent's timeline. A fixed number of queries, however long the life.
"""

from dataclasses import dataclass, field

from django.db.models import Prefetch
from django.utils.translation import gettext as _, pgettext

from cmnsd.models.access import filter_accessible


@dataclass
class Entry:
  event: object
  relative: object = None      # for a family event: whose it is
  relation: str = ''           # 'son', 'mother', ... (the relative to this person)
  age: str = ''                # 'aged 28', 'about 28'
  history: bool = False        # a general event without people, in their lifetime
  others: list = field(default_factory=list)   # the event's other people (named as the viewer may see them, by the template)


def _placed(entry):
  """Whether an entry has a place in time: a date (a year at least) - or,
  undated, the person's own birth or death, which have one anyway: a life's
  first and last event (so a birth can carry its notes and comments
  without a guessed year). Other undated events have no place in a
  timeline and are left out of it."""
  from events.models import Event
  own_end = entry.relative is None and entry.event.kind in (Event.Kind.BIRTH, Event.Kind.DEATH)
  return entry.event.year is not None or own_end


def _entry_key(entry):
  """By date; an undated own birth first, an undated own death last."""
  from events.models import Event
  event = entry.event
  if event.year is None:
    rank = 0 if event.kind == Event.Kind.BIRTH else 2
  else:
    rank = 1
  return (rank, event.year or 0, event.month or 0, event.day or 0)


def _relation(kind, person):
  """The relative's relation to the person, by the relative's gender."""
  words = {
    'child': {'m': pgettext('relation', "son"), 'f': pgettext('relation', "daughter")},
    'parent': {'m': pgettext('relation', "father"), 'f': pgettext('relation', "mother")},
    'partner': {'m': pgettext('relation', "husband"), 'f': pgettext('relation', "wife")},
  }
  fallback = {'child': pgettext('relation', "child"), 'parent': pgettext('relation', "parent"), 'partner': pgettext('relation', "partner")}
  return words[kind].get(person.gender, fallback[kind])


def age_at(birth, event):
  """'aged 28' / 'about 28' - the age at `event` from `birth` (both
  PartialDateMixin), '' when a year is missing or it's before the birth.
  'about' when either date is circa or incomplete, so the year difference
  may be one off. None when either is 'before' or 'after': that can be
  years off, and a bound ("at least 14" at a marriage) reads as a
  judgement - so no age rather than a misleading one."""
  open_ended = (birth.DateQualifier.BEFORE, birth.DateQualifier.AFTER) if birth else ()
  if not (birth and birth.year and event.year) or birth.date_qualifier in open_ended or event.date_qualifier in open_ended:
    return ''
  years = event.year - birth.year
  complete = all((birth.month, birth.day, event.month, event.day))
  if complete and (event.month, event.day) < (birth.month, birth.day):
    years -= 1
  if years < 0 or (years == 0 and event.pk == birth.pk):
    return ''
  if complete and birth.is_exact_date() and event.is_exact_date():
    return _("aged %(years)s") % {'years': years}
  return _("about %(years)s") % {'years': years}


def life_timeline(person, request):
  """[Entry] - the person's own events and their close family's, by date;
  undated ones only for the person's own birth and death (_placed)."""
  from content.models import Content
  from events.models import Event
  from .models import Person

  content = Prefetch('content', queryset=Content.objects.visible_to(request), to_attr='visible_content')
  visible_people = filter_accessible(Person.objects.all(), request)
  events = filter_accessible(Event.objects.all(), request).prefetch_related(content, 'places__parent', 'people')

  own = list(events.filter(people=person))
  birth = next((e for e in own if e.kind == Event.Kind.BIRTH), None)
  death = next((e for e in own if e.kind == Event.Kind.DEATH), None)

  # Close family, as far as this viewer may see them.
  family = {}
  for kind, relatives in (
    ('child', person._get_children_flat()), ('parent', person._get_parents_flat()), ('partner', person.get_partners()),
  ):
    for relative in relatives:
      family[relative.pk] = (kind, relative)
  visible_ids = set(visible_people.filter(pk__in=family).values_list('pk', flat=True))
  wanted = {
    'child': (Event.Kind.BIRTH, Event.Kind.DEATH),
    'parent': (Event.Kind.DEATH,),
    'partner': (Event.Kind.DEATH,),
  }
  own_ids = {e.pk for e in own}
  family_entries = []
  for event in events.filter(people__in=visible_ids, kind__in=(Event.Kind.BIRTH, Event.Kind.DEATH)).exclude(pk__in=own_ids).distinct():
    # Within the person's life, when its ends are known.
    if event.year and ((birth and birth.year and event.year < birth.year) or (death and death.year and event.year > death.year)):
      continue
    for relative in event.people.all():
      if relative.pk in visible_ids and event.kind in wanted[family[relative.pk][0]]:
        kind = family[relative.pk][0]
        family_entries.append(Entry(event, relative=relative, relation=_relation(kind, relative)))
        break

  # History: historical events without people, dated within the life - from
  # the birth year to the death year (unknown: a hundred years on, or
  # today). Without a birth year there's no life to place them in.
  history_entries = []
  if birth and birth.year:
    from datetime import date
    last = death.year if death and death.year else min(birth.year + 100, date.today().year)
    history_entries = [
      Entry(event, history=True)
      for event in events.filter(kind=Event.Kind.HISTORICAL, people__isnull=True, year__gte=birth.year, year__lte=last)
    ]

  entries = [entry for entry in [Entry(event) for event in own] + family_entries + history_entries if _placed(entry)]
  for entry in entries:
    entry.age = age_at(birth, entry.event)
    # Who else is in it - not the person (it's their page), not the relative
    # (named with the relation already).
    entry.others = [
      p for p in entry.event.people.all()
      if p.pk != person.pk and (entry.relative is None or p.pk != entry.relative.pk)
    ]
  # Spouses' ages at a marriage (event/_event.html): their births in one query.
  Person._attach_lifespan([p for entry in entries if entry.event.kind == Event.Kind.MARRIAGE for p in entry.others])
  return sorted(entries, key=_entry_key)
