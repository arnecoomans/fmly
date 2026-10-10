"""
Progress behind the loose ends: what's done, not only what's missing - a
thin bar under a loose end on the dashboard, with a legend on its page.

A bar is about a whole (the family's people, the scanned documents, the
photos, the events), split into parts. Two loose ends about the same
whole share one bar (GROUPS): people without a birth and without a death
in four parts, documents without a transcript and transcripts to check in
three. People without parents has a bar of two parts: done - "fine as it
is" included - and still to do. The others have none: little work left,
or no whole to measure against.

Only what this viewer may see, as the loose ends themselves.
"""

from django.db import models
from django.utils.translation import gettext as _

from cmnsd.models.access import filter_accessible

# Loose ends that share a bar; the bar goes under the last of them shown.
GROUPS = {
  'no-birth': 'people', 'no-death': 'people',
  'no-transcript': 'documents', 'open-transcripts': 'documents',
}
# Loose ends with a bar of their own: done / to do. Only where there's a fair
# amount of work: photos without people matter less, and undated or
# untitled events are to be resolved down to none - a bar adds nothing.
SINGLE = ('no-parents',)

IMAGE_FILES = r'\.(jpe?g|png|gif|webp|tiff?)$'


def has_bar(name):
  return name in GROUPS or name in SINGLE


def bar(name, request):
  """{'segments': [{'key', 'label', 'count', 'percent'}], 'total', 'summary'}
  for a loose end - its group's bar, or its own - or None."""
  if name in GROUPS:
    parts = _people(request) if GROUPS[name] == 'people' else _documents(request)
  elif name in SINGLE:
    parts = _single(name, request)
  else:
    return None
  return _bar(parts, done_key=parts[0][0] if name in SINGLE else None)


def _bar(parts, done_key=None):
  """parts: [(key, label, count)], the done part first."""
  total = sum(count for _key, _label, count in parts)
  if not total:
    return None
  segments = [
    # As text with a point: a localised float (a comma in Dutch) isn't CSS.
    {'key': key, 'label': label, 'count': count, 'percent': f'{100 * count / total:.2f}'}
    for key, label, count in parts if count
  ]
  if done_key:
    done = parts[0][2]
    summary = _("%(done)s of %(total)s done (%(percent)s%%)") % {'done': done, 'total': total, 'percent': round(100 * done / total)}
  else:
    summary = ' · '.join(f"{label} {count}" for _key, label, count in parts if count)
  return {'segments': segments, 'total': total, 'summary': summary}


def _people(request):
  """Family and possibly family (an outsider is in the archive for another
  reason): their birth and death records - a death without a date counts."""
  from events.models import Event
  from people.models import Person
  people = filter_accessible(Person.objects.all(), request).exclude(family_connection=Person.FamilyConnection.OUTSIDER)
  births = Event.objects.current().filter(kind=Event.Kind.BIRTH).values('people')
  deaths = Event.objects.current().filter(kind=Event.Kind.DEATH).values('people')
  born, died = people.filter(pk__in=births), people.exclude(pk__in=births)
  return [
    ('both', _("birth and death"), born.filter(pk__in=deaths).count()),
    ('birth', _("birth only"), born.exclude(pk__in=deaths).count()),
    ('death', _("death only"), died.filter(pk__in=deaths).count()),
    ('none', _("neither"), died.exclude(pk__in=deaths).count()),
  ]


def _documents(request):
  """The scanned documents (images - the transcribe page doesn't do PDF
  pages yet), as the "without a transcript" loose end: transcribed and
  checked, a transcript to finish or check, none."""
  from content.models import Content, Transcript
  from .blocks import NO_TRANSCRIPT_KINDS
  documents = (
    Content.objects.visible_to(request).listable().filter(kind=Content.Kind.DOCUMENT, file__iregex=IMAGE_FILES)
    .exclude(document_detail__document_kind__in=NO_TRANSCRIPT_KINDS)   # a form: tagged, not transcribed
  )
  open_ = Transcript.objects.filter(models.Q(incomplete=True) | models.Q(method=Transcript.Method.AUTOMATIC)).values('content')
  with_transcript = documents.filter(transcripts__isnull=False).distinct()
  return [
    ('done', _("transcribed"), with_transcript.exclude(pk__in=open_).count()),
    ('open', _("to finish or check"), with_transcript.filter(pk__in=open_).count()),
    ('none', _("no transcript"), documents.filter(transcripts__isnull=True).count()),
  ]


def _single(name, request):
  """The whole a loose end is part of; done = the whole less what's still
  on the list (so "fine as it is" counts as done)."""
  from people.models import Person
  from .blocks import loose_end_items
  whole = filter_accessible(Person.objects.all(), request).filter(family_connection='family')   # no-parents
  total = whole.distinct().count()
  todo = loose_end_items(name, request).distinct().count()
  return [('done', _("done"), total - todo), ('none', _("to do"), todo)]


def attach(rows, request):
  """The dashboard's loose ends [(name, label, count)] -> [(name, label,
  count, bar)]: a group's bar under the last of its loose ends shown, a
  single bar under its own."""
  last = {GROUPS[name]: name for name, _label, _count in rows if name in GROUPS}
  out = []
  for name, label, count in rows:
    shown = (name in GROUPS and last[GROUPS[name]] == name) or name in SINGLE
    out.append((name, label, count, bar(name, request) if shown else None))
  return out
