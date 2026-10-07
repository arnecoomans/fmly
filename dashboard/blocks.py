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

def on_this_day(request, today=None):
  """(events, label): what happened on today's date across the years - or, on a day without any, those of the coming week. The
  rules (what's shown) are events/anniversaries.py's."""
  from events.anniversaries import anniversaries
  today = today or date.today()
  events = anniversaries(request, days=[today])
  if events:
    return events, _("on this day")
  return anniversaries(request, days=[today + timedelta(days=n) for n in range(1, 8)]), _("this coming week")


def recently_added(request, count=10):
  """The newest published items (wholes) this viewer may see - ten: two
  rows of five, or of four (the last two hidden) on a narrower block."""
  from content.models import Content
  return list(
    Content.objects.visible_to(request).listable().filter(status=Content.Status.PUBLISHED)
    .select_related('photo_detail', 'document_detail').order_by('-date_created')[:count]
  )


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
  about them (comments, notes, tags)."""
  from content.models import Content
  from core.comments import visible_comment_feed
  from core.models import Tag
  from events.models import Event
  from notes.models import Note
  from people.models import Person
  from places.models import Place
  return {
    'people': filter_accessible(Person.objects.all(), request).count(),
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
  'no-parents': _("people without parents"),
  'photos-without-people': _("photos without people"),
  'undated-events': _("events without a date"),
  'other-events': _("events of kind 'other' without a title"),
  'open-transcripts': _("transcripts to finish or check"),
  'no-transcript': _("documents without a transcript"),
  'low-resolution': _("images in low resolution"),
}

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
  if name == 'no-parents':
    return people.exclude(relations_to__relation_type='parent').filter(family_connection='family')
  if name == 'photos-without-people':
    return Content.objects.visible_to(request).listable().filter(kind=Content.Kind.PHOTO, people__isnull=True)
  if name == 'undated-events':
    return events.filter(year__isnull=True)
  if name == 'other-events':
    return events.filter(kind='other', title='')
  if name == 'low-resolution':
    # Smallest first (Content.width/height, as shown).
    return (
      Content.objects.visible_to(request).filter(width__isnull=False, height__isnull=False)
      .annotate(pixels=models.F('width') * models.F('height')).filter(pixels__lt=LOW_RESOLUTION_PIXELS)
      .order_by('pixels', 'name')
    )
  if name == 'no-transcript':
    # Scanned documents nobody transcribed yet - images only: the transcribe
    # page doesn't do PDF pages yet. Newest first.
    return (
      Content.objects.visible_to(request).listable()
      .filter(kind=Content.Kind.DOCUMENT, file__iregex=r'\.(jpe?g|png|gif|webp|tiff?)$', transcripts__isnull=True)
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


def undated_by_person(events, request):
  """The undated events in one list, each person's together - their birth
  first, death last - people by name (as the people list), each event
  once (a marriage under the first of its people); events without people
  this viewer may see last."""
  from people.models import Person
  events = list(events.prefetch_related('people'))
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
  """[(name, label, count)] for an editor - only the ones not empty."""
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
  return rows


def you(request):
  """The viewer's own record, when their account is linked to a person."""
  person = getattr(request.user, 'person', None) if request.user.is_authenticated else None
  if person is None:
    return None
  from content.models import Content
  return {'person': person, 'content': Content.objects.visible_to(request).filter(people=person).count()}
