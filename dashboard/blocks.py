"""
What the dashboard shows - one function per block, each only what the
viewer may see (status + visibility, cmnsd filter_accessible; an event
through its people). The reading blocks are for everyone; the work blocks
(inbox, notes, loose ends) only for someone who edits.
"""

from datetime import date, timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _

from cmnsd.models.access import filter_accessible

# The dashboard's anniversaries: a teaser to the archive - the milestones of
# a life and history. A migration, a career step, an engagement matter once
# someone interests you: on their page and in the calendar, not here.
ANNIVERSARY_KINDS = ('birth', 'death', 'marriage', 'historical')


def on_this_day(request, today=None):
  """(today's, the coming week's): what happened on today's date across
  the years, and on the seven days after it - the week always, so the
  block doesn't change shape from one day to the next; today's above it
  when there are any. Births, deaths, marriages and history only
  (ANNIVERSARY_KINDS); the rest of the rules are events/anniversaries.py's."""
  from events.anniversaries import anniversaries
  today = today or date.today()
  return (
    anniversaries(request, days=[today], kinds=ANNIVERSARY_KINDS),
    anniversaries(request, days=[today + timedelta(days=n) for n in range(1, 8)], kinds=ANNIVERSARY_KINDS),
  )


def recently_added(request, count=10):
  """The newest published items (wholes) this viewer may see - ten: two
  rows of five, or of four (the last two hidden) on a narrower block."""
  from content.models import Content
  return list(
    Content.objects.visible_to(request).listable().filter(status=Content.Status.PUBLISHED)
    .select_related('photo_detail', 'document_detail').order_by('-date_created')[:count]
  )


def family_favorites(request, count=10):
  """What stands out: the items with the most favorites (core/favorites.py)
  - ten, as recently added."""
  from core.favorites import family_favorites as favorites
  return favorites(request, count)


def conversation(request, count=3):
  """The latest comments this viewer may see (core/comments.py)."""
  if not request.user.is_authenticated:
    return []
  from core.comments import visible_comment_feed
  return list(visible_comment_feed(request)[:count])


def from_the_archive(request):
  """One image at random, from what this viewer may see."""
  from content.models import Content
  items = Content.objects.visible_to(request).listable().filter(status=Content.Status.PUBLISHED, kind=Content.Kind.PHOTO).exclude(file='')
  return items.order_by('?').first()


def numbers(request):
  """The archive in numbers - each as far as this viewer may see it: the
  things in it (people, items, events, places) and what's said and found
  about them (comments, notes, tags). People: family only, as the People
  list it links to shows by default - outsiders (authors, neighbours) and
  possibly family are in the archive for another reason."""
  from content.models import Content
  from core.comments import visible_comment_feed
  from core.models import Tag
  from events.models import Event
  from notes.models import Note
  from people.models import Person
  from places.models import Place
  return {
    'people': filter_accessible(Person.objects.filter(family_connection=Person.FamilyConnection.FAMILY), request).count(),
    'content': Content.objects.visible_to(request).listable().count(),
    'events': Event.objects.filter(pk__in=filter_accessible(Event.objects.all(), request).values('pk')).count(),
    'places': Place.objects.count(),
    'comments': visible_comment_feed(request).count(),
    'notes': filter_accessible(Note.objects.all(), request).count(),
    'tags': filter_accessible(Tag.objects.all(), request).count(),
  }


def your_work(request):
  """For someone who edits: the inbox, their open notes."""
  from content.views.upload import inbox_items
  from notes.models import Note
  user = request.user
  if not user.is_authenticated:
    return None
  work = {}
  if user.has_perm('content.add_content'):
    from content.views.upload import inbox_total
    drafts = inbox_items(user)
    work['inbox'] = {'count': inbox_total(user), 'latest': list(drafts.order_by('-date_created', '-pk')[:5])}
  if user.has_perm('notes.add_note'):
    work['notes'] = list(Note.objects.visible_to(request).filter(user=user, kind__in=(Note.Kind.TODO, Note.Kind.QUESTION)).in_order()[:5])
  return work or None


# Loose ends: what's missing, each a filtered list (dashboard/loose-ends/<name>/).
LOOSE_ENDS = {
  'marked': _("marked as a loose end"),
  'no-birth': _("people without a birth"),
  'no-death': _("people born over 100 years ago without a death"),
  'no-parents': _("people without parents"),
  'photos-without-people': _("photos without people"),
  'people-without-role': _("people on items without a role"),
  'undated-events': _("events without a date"),
  'other-events': _("events of kind 'other' - does a kind fit?"),
  'undocumented-events': _("events without documentation"),
  'open-transcripts': _("transcripts to finish or check"),
  'no-transcript': _("documents without a transcript"),
  'low-resolution': _("images in low resolution"),
  'lone-places': _("places on their own (no parent, nothing under them)"),
}

# Document kinds whose value is a few facts, not their text: an identity
# document - a passport application, an ID card - is a form; its people are
# tagged and its facts go to them (birth, profession). Not "without a
# transcript", and not counted in the documents bar (dashboard/progress.py).
NO_TRANSCRIPT_KINDS = ('identity',)

# Below this many pixels an image is a loose end: a better scan or original
# is worth looking for. Total pixels, not the short side - a newspaper
# clipping is a narrow strip by nature. 0.5 MP is about 800 x 600.
LOW_RESOLUTION_PIXELS = 500_000


def marked_loose_ends(request):
  """What's tagged "Loose end" (core.tags.LOOSE_END_SLUG), as this viewer
  may see it: {'people', 'content', 'notes'}."""
  from content.models import Content
  from core.tags import loose_end_tag
  from notes.models import Note
  from people.models import Person
  tag = loose_end_tag()
  if tag is None:
    return {'people': [], 'content': [], 'notes': []}
  return {
    'people': list(filter_accessible(Person.objects.filter(tags=tag), request)),
    'content': list(Content.objects.visible_to(request).filter(tags=tag)),
    'notes': list(Note.objects.visible_to(request).filter(tags=tag)),
  }


DISMISSABLE = lambda name: name in LOOSE_ENDS and name != 'marked'   # marked: remove the tag instead


def loose_end_items(name, request, dismissed=False):
  """The objects behind a loose end - only what this viewer may see, less
  those dismissed from it ("fine as it is", LooseEndDismissal); with
  dismissed=True only those. (The marked ones are of several kinds:
  marked_loose_ends - not dismissable: removing the tag is how.)"""
  items = _loose_end_queryset(name, request)
  if items is None:
    return None
  from django.contrib.contenttypes.models import ContentType
  from .models import LooseEndDismissal
  ids = LooseEndDismissal.objects.filter(name=name, content_type=ContentType.objects.get_for_model(items.model)).values('object_id')
  return items.filter(pk__in=ids) if dismissed else items.exclude(pk__in=ids)


def role_items(request):
  """The items with someone on them this viewer may see - the whole of the
  "without a role" loose end (its bar, dashboard/progress.py)."""
  from content.models import Content
  from people.models import Person
  people = filter_accessible(Person.objects.all(), request)
  return Content.objects.visible_to(request).filter(person_links__person__in=people).distinct()


def _loose_end_queryset(name, request):
  """Each loose end's own rule, before dismissals."""
  from content.models import Content
  from events.models import Event
  from people.models import Person
  people = filter_accessible(Person.objects.all(), request)
  events = filter_accessible(Event.objects.all(), request)
  if name == 'no-birth':
    # Family and possibly family: an outsider (an author, a neighbour) is in
    # the archive for another reason - their birth isn't missing.
    return people.exclude(family_connection=Person.FamilyConnection.OUTSIDER).exclude(
      pk__in=Event.objects.current().filter(kind='birth').values('people'),
    )
  if name == 'no-death':
    # Born more than a century ago, no death on record - not even one
    # without a date ("died, details unknown"). Family and possibly family,
    # as no-birth; without a birth year there's nothing to go by.
    long_ago = Event.objects.current().filter(kind='birth', year__lte=date.today().year - 100).values('people')
    died = Event.objects.current().filter(kind='death').values('people')
    return people.exclude(family_connection=Person.FamilyConnection.OUTSIDER).filter(pk__in=long_ago).exclude(pk__in=died)
  if name == 'no-parents':
    return people.exclude(relations_to__relation_type='parent').filter(family_connection='family')
  if name == 'photos-without-people':
    return Content.objects.visible_to(request).listable().filter(kind=Content.Kind.PHOTO, people__isnull=True)
  if name == 'undocumented-events':
    # Proven events: an item documenting it (the event page's "documented
    # by") - as far as this viewer may see: what they can't see doesn't
    # count, nor leak. Not history: its source goes in its description.
    from content.models import Content
    return documentable_events(events).exclude(content__in=Content.objects.visible_to(request)).distinct()
  if name == 'people-without-role':
    # An item with someone on it whose role isn't set (ContentPerson, issue
    # #471) - only people this viewer may see: they can't set the role of
    # someone hidden. Parts too: a person can be on a page. With the count.
    return role_items(request).filter(person_links__role='', person_links__person__in=people).select_related('photo_detail', 'document_detail').annotate(
      without_role=models.Count('person_links', filter=models.Q(person_links__role='', person_links__person__in=people), distinct=True),
    )
  if name == 'undated-events':
    return events.filter(year__isnull=True)
  if name == 'other-events':
    # A migration or residence entered as 'other' ("Aankomst per Sibajak"):
    # give it its kind - or "fine as it is" for what really is something else.
    return events.filter(kind='other')
  if name == 'lone-places':
    # Outside the place tree: a town that belongs under its country, or a
    # country with nothing under it yet ("fine as it is"). Places have no
    # visibility of their own - every editor sees them all.
    from places.models import Place
    return Place.objects.filter(parent__isnull=True, children__isnull=True).order_by('name')
  if name == 'low-resolution':
    # Smallest first (Content.width/height, as shown).
    return (
      Content.objects.visible_to(request).filter(width__isnull=False, height__isnull=False)
      .annotate(pixels=models.F('width') * models.F('height')).filter(pixels__lt=LOW_RESOLUTION_PIXELS)
      .order_by('pixels', 'name')
    )
  if name == 'no-transcript':
    # Scanned documents nobody transcribed yet - images only: the transcribe
    # page doesn't do PDF pages yet; not the kinds that need none
    # (NO_TRANSCRIPT_KINDS). Newest first.
    return (
      Content.objects.visible_to(request).listable()
      .filter(kind=Content.Kind.DOCUMENT, file__iregex=r'\.(jpe?g|png|gif|webp|tiff?)$', transcripts__isnull=True)
      .exclude(document_detail__document_kind__in=NO_TRANSCRIPT_KINDS)
      .order_by('-date_created', '-pk')
    )
  if name == 'open-transcripts':
    # A transcript marked incomplete, or an automatic one nobody checked -
    # each item once, with why (open_incomplete / open_unchecked), oldest first.
    from content.models import Transcript
    mine = Transcript.objects.filter(content=models.OuterRef('pk'))
    incomplete = models.Exists(mine.filter(incomplete=True))
    unchecked = models.Exists(mine.filter(method=Transcript.Method.AUTOMATIC))
    return (
      Content.objects.visible_to(request)
      .annotate(open_incomplete=incomplete, open_unchecked=unchecked)
      .filter(models.Q(open_incomplete=True) | models.Q(open_unchecked=True))
      .order_by('date_created', 'pk')
    )
  return None


def documentable_events(events):
  """The events a document can prove: those with people, not history."""
  from events.models import Event
  return events.exclude(kind=Event.Kind.HISTORICAL).filter(people__isnull=False).distinct()


def events_by_person(events, request):
  """Events in one list, each person's together - their birth
  first, death last - people by name (as the people list), each event
  once (a marriage under the first of its people); events without people
  this viewer may see last."""
  from people.models import Person
  # Rendered as event rows (event/_event.html): places named in full, and
  # spouses' ages at a marriage - preloaded, not a query each.
  events = list(events.prefetch_related('people', 'places__parent__parent'))
  Person._attach_lifespan([p for event in events if event.kind == 'marriage' for p in event.people.all()])
  visible = set(filter_accessible(Person.objects.all(), request).filter(
    pk__in=[p.pk for event in events for p in event.people.all()],
  ).values_list('pk', flat=True))
  life_order = {'birth': 0, 'death': 2}

  def name_key(person):
    return ((person.last_name or person.married_name or '').casefold(), (person.given_name or '').casefold(), person.pk)

  def first_person(event):
    shown = [p for p in event.people.all() if p.pk in visible]
    return min(shown, key=name_key) if shown else None

  def key(event):
    person = first_person(event)
    return (person is None, name_key(person) if person else ('', '', 0), life_order.get(event.kind, 1))

  return sorted(events, key=key)


def is_editor(user):
  """Someone who maintains the archive: loose ends are theirs to fix."""
  return bool(user and user.is_authenticated and (user.has_perm('people.change_person') or user.has_perm('content.change_content')))


def loose_ends(request):
  """[(name, label, count, bar)] for an editor - only the ones not empty;
  bar: its progress (dashboard/progress.py), or None."""
  if not is_editor(request.user):
    return []
  rows = []
  for name, label in LOOSE_ENDS.items():
    if name == 'marked':
      count = sum(len(objects) for objects in marked_loose_ends(request).values())
    else:
      count = loose_end_items(name, request).distinct().count()
    if count:
      rows.append((name, label, count))
  from .progress import attach
  return attach(rows, request)


def you(request):
  """The viewer's own record, when their account is linked to a person."""
  person = getattr(request.user, 'person', None) if request.user.is_authenticated else None
  if person is None:
    return None
  from content.models import Content
  return {'person': person, 'content': Content.objects.visible_to(request).filter(people=person).count()}
