"""
A person's life as a timeline (the Events section of their page): their own
events - birth, marriages, migrations, death, ... - those of their close
family that fall within their life: children's births and deaths, parents'
and partners' deaths - the background of their own events, and the history
around it. Each entry knows the person's age at it, when both dates are
known.

History and background (issue #464):
- background: an event that's background for one of the person's own
  events (Event.background_for - "Sibajak released for repatriation" for
  "Arrival per Sibajak") - shown also outside their life, it was linked
  on purpose; just before what it explains when undated. One way and one
  step: being in the background event doesn't bring what it explains.
- history: historical events dated within their life that aren't
  background for an event with people - linked to one, a historical event
  is specific context, shown only through its link. Also when it has
  people: theirs as their own event, history for everyone else.

Only what this viewer may see: an event by its visibility (through its
people), a relative only when visible - a hidden child's birth doesn't show
up in a parent's timeline. A fixed number of queries, however long the life.
"""

from collections import defaultdict
from dataclasses import dataclass, field

from django.db.models import Exists, OuterRef, Prefetch, Q
from django.utils.translation import gettext as _, pgettext

from cmnsd.models.access import filter_accessible


@dataclass
class Entry:
  event: object
  relative: object = None      # for a family event: whose it is
  relation: str = ''           # 'son', 'mother', ... (the relative to this person)
  age: str = ''                # 'aged 28', 'about 28'
  history: bool = False        # a general historical event, in their lifetime
  background: bool = False     # background for one of their own events
  explains: list = field(default_factory=list)  # for background: those own events, by date
  others: list = field(default_factory=list)   # the event's other people (named as the viewer may see them, by the template)
  same_day: bool = False       # on the exact date of the row before it (mark_same_day)


def mark_same_day(entries):
  """entry.same_day for a row on the very date of the row before it - only
  a complete, exact date (a year, or "ca.", isn't a moment), and only within
  its group (history or their own life), so it never points at a row the
  toggle hides. Twins, a mother dying the day her child is born, a double
  wedding: connections that take effort to spot when each row repeats the
  date."""
  previous = {}
  for entry in entries:
    event = entry.event
    group = entry.history
    exact = event.year and event.month and event.day and event.date_qualifier == 'exact'
    key = (event.year, event.month, event.day) if exact else None
    entry.same_day = key is not None and previous.get(group) == key
    previous[group] = key
  return entries


def _placed(entry):
  """Whether an entry has a place in time: a date (a year at least) - or,
  undated, the person's own birth or death, which have one anyway: a life's
  first and last event (so a birth can carry its notes and comments
  without a guessed year) - and background, which goes with what it
  explains. Other undated events have no place in a timeline and are left
  out of it."""
  from events.models import Event
  own_end = entry.relative is None and not entry.history and not entry.background and entry.event.kind in (Event.Kind.BIRTH, Event.Kind.DEATH)
  return entry.event.year is not None or own_end or entry.background


def _entry_key(entry):
  """By date; an undated own birth first, an undated own death last. An
  undated background entry takes the date of what it explains; on the same
  date, background comes just before."""
  from events.models import Event
  event = entry.event
  if event.year is None and entry.background and entry.explains:
    event = entry.explains[0]
  if event.year is None:
    rank = 0 if event.kind == Event.Kind.BIRTH else 2
  else:
    rank = 1
  return (rank, event.year or 0, event.month or 0, event.day or 0, 0 if entry.background else 1)


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
  """[Entry] - the person's own events, their close family's, the
  background of their own and the history around them, by date; undated
  ones only for the person's own birth and death, and background (_placed)."""
  from content.models import Content
  from events.models import Event
  from .models import Person

  content = Prefetch('content', queryset=Content.objects.visible_to(request), to_attr='visible_content')
  visible_people = filter_accessible(Person.objects.all(), request)
  events = filter_accessible(Event.objects.all(), request).prefetch_related(content, 'places__parent__parent', 'people')

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

  # One query for all three - the person's own events, the family's births
  # and deaths, history - sorted out below; each its own query would
  # repeat the prefetches above. History by year in Python: few events.
  # is_background: background for some event with people - then not general
  # history. For an event without people it changes nothing here.
  ends = (Event.Kind.BIRTH, Event.Kind.DEATH)
  links = Event.background_for.through
  candidates = list(events.filter(
    Q(people=person) | Q(people__in=visible_ids, kind__in=ends) | Q(kind=Event.Kind.HISTORICAL)
  ).annotate(is_background=Exists(links.objects.filter(from_event=OuterRef('pk'), to_event__people__isnull=False))).distinct())
  own = [e for e in candidates if any(p.pk == person.pk for p in e.people.all())]
  birth = next((e for e in own if e.kind == Event.Kind.BIRTH), None)
  death = next((e for e in own if e.kind == Event.Kind.DEATH), None)

  own_ids = {e.pk for e in own}
  family_entries = []
  for event in candidates:
    if event.pk in own_ids or event.kind not in ends:
      continue
    # Within the person's life, when its ends are known.
    if event.year and ((birth and birth.year and event.year < birth.year) or (death and death.year and event.year > death.year)):
      continue
    for relative in event.people.all():
      if relative.pk in visible_ids and event.kind in wanted[family[relative.pk][0]]:
        kind = family[relative.pk][0]
        family_entries.append(Entry(event, relative=relative, relation=_relation(kind, relative)))
        break

  # History: historical events dated within the life - from the birth year
  # to the death year (unknown: a hundred years on, or today) - that aren't
  # background for anything, and not the person's own. Without a birth
  # year there's no life to place them in.
  history_entries = []
  if birth and birth.year:
    from datetime import date
    last = death.year if death and death.year else min(birth.year + 100, date.today().year)
    history_entries = [
      Entry(event, history=True) for event in candidates
      if event.kind == Event.Kind.HISTORICAL and event.pk not in own_ids and not event.is_background
      and event.year is not None and birth.year <= event.year <= last
    ]

  # Background of the person's own events: which, from the link table (one
  # query); the events themselves only when there are any - visible ones,
  # not the person's own (no doubles), whatever their date.
  background_entries = []
  pairs = links.objects.filter(to_event__in=own_ids).exclude(from_event__in=own_ids).values_list('from_event', 'to_event')
  explained = defaultdict(list)
  own_by_pk = {e.pk: e for e in own}
  for from_id, to_id in pairs:
    explained[from_id].append(own_by_pk[to_id])
  if explained:
    for event in events.filter(pk__in=explained):
      what = sorted(explained[event.pk], key=lambda e: (e.year is None, e.year or 0, e.month or 0, e.day or 0))
      background_entries.append(Entry(event, background=True, explains=what))

  entries = [entry for entry in [Entry(event) for event in own] + family_entries + history_entries + background_entries if _placed(entry)]
  for entry in entries:
    entry.age = age_at(birth, entry.event)
    # Who else is in it - not the person (it's their page), not the relative
    # (named with the relation already).
    entry.others = [
      p for p in entry.event.people.all()
      if p.pk != person.pk and (entry.relative is None or p.pk != entry.relative.pk)
    ]
  # Spouses' ages at a marriage (event/_event.html): their births in one
  # query - none for a partner whose births get_partners() already has.
  known = {relative.pk: relative for _, relative in family.values() if hasattr(relative, '_prefetched_birth')}
  spouses = []
  for p in (p for entry in entries if entry.event.kind == Event.Kind.MARRIAGE for p in entry.others):
    if p.pk in known:
      p._prefetched_birth, p._prefetched_death = known[p.pk]._prefetched_birth, known[p.pk]._prefetched_death
    else:
      spouses.append(p)
  Person._attach_lifespan(spouses)
  return mark_same_day(sorted(entries, key=_entry_key))
