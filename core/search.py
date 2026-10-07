"""
Search across the archive (/search/, core.views.SearchView): one query,
every kind - people, content, events, notes, places, tags - each through
its own list search (cmnsd.api.filtering.build_list: the model's
search_fields and api_search_q, visibility first), so /search/ finds what
the people list, the content list and the API find for the same words.

Each section is ranked like a picker - a name that starts with the search
first (cmnsd rank_by_name) - and shows the first few; "show all" is the
same page narrowed to one kind (?kind=). A hit found in its text rather
than its name - a transcript, a biography, a note's body - gets a snippet
around the word, so it's clear why it's there.
"""

import re
from dataclasses import dataclass

from django.http import QueryDict
from django.utils.translation import gettext_lazy as _

from cmnsd.api.filtering import build_list, search_character
from cmnsd.views.api.object_list import rank_by_name

MIN_LENGTH = 2      # one letter finds half the archive
PER_SECTION = 5     # on the overview
PER_KIND = 100      # narrowed to one kind
SNIPPET_BEFORE, SNIPPET_AFTER = 60, 120


@dataclass
class Section:
  kind: str
  label: str
  icon: str
  hits: list
  count: int
  more: bool = False


def kinds():
  """(kind, model, label, icon) in the order the page shows them."""
  from content.models import Content
  from events.models import Event
  from notes.models import Note
  from people.models import Person
  from places.models import Place
  from .models import Tag
  return [
    ('person', Person, _("people"), 'people'),
    ('content', Content, _("content"), 'collection'),
    ('event', Event, _("events"), 'calendar-event'),
    ('note', Note, _("notes"), 'journal-text'),
    ('place', Place, _("places"), 'geo-alt'),
    ('tag', Tag, _("tags"), 'tag'),
  ]


def search(request, query, kind=None):
  """[Section] - the kinds with hits for `query` (only `kind`, if given
  and known), each ranked and cut to PER_SECTION (PER_KIND for one kind)."""
  query = ' '.join(query.split())
  if len(query) < MIN_LENGTH:
    return []
  params = QueryDict(mutable=True)
  params[search_character()] = query
  known = {name for name, *_rest in kinds()}
  sections = []
  for name, model, label, icon in kinds():
    if kind in known and name != kind:
      continue
    objects = list(build_list(model, request, params=params)['objects'])
    if not objects:
      continue
    limit = PER_KIND if kind in known else PER_SECTION
    hits = rank_by_name(objects, query, request)[:limit]
    for hit in hits:
      hit.search_snippet = snippet(hit, query, request)
    sections.append(Section(name, label, icon, hits, len(objects), more=len(objects) > limit))
  return sections


def _texts(obj, request):
  """The longer texts an object is found by, besides its name."""
  from content.models import Content
  from events.models import Event
  from notes.models import Note
  from people.models import Person
  if isinstance(obj, Person):
    return [obj.biography]
  if isinstance(obj, Content):
    # Its own transcripts, then its visible parts' - as Content.api_search_q.
    from content.models import Transcript
    parts = Content.objects.visible_to(request).filter(parent=obj)
    transcripts = Transcript.objects.filter(content__in=[obj.pk, *parts.values_list('pk', flat=True)])
    return [obj.description, *transcripts.order_by('content__position', 'pk').values_list('text', flat=True)]
  if isinstance(obj, Event):
    return [obj.description]
  if isinstance(obj, Note):
    return [obj.body]
  return []


_MARKDOWN_LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')
_MARKDOWN_MARKS = re.compile(r'[*_#>`]+')


def _plain(text):
  text = _MARKDOWN_LINK.sub(r'\1', text or '')
  return ' '.join(_MARKDOWN_MARKS.sub('', text).split())


def snippet(obj, query, request):
  """'... the words around the hit ...' - when a search word isn't in the
  object's name, from the first of its texts that holds one; '' when the
  name explains the hit."""
  name = str(obj).casefold()
  missing = [term for term in query.split() if term.casefold() not in name]
  if not missing:
    return ''
  term = missing[0].casefold()
  for raw in _texts(obj, request):
    # Readable text first; the raw text when the word is only in markup
    # (a link's address).
    text = _plain(raw)
    if term not in text.casefold():
      text = ' '.join((raw or '').split())
    at = text.casefold().find(term)
    if at < 0:
      continue
    start, end = max(0, at - SNIPPET_BEFORE), min(len(text), at + SNIPPET_AFTER)
    # Whole words at the cut edges.
    if start > 0 and (space := text.find(' ', start, at)) >= 0:
      start = space + 1
    if end < len(text) and (space := text.rfind(' ', at, end)) > at:
      end = space
    return ('… ' if start > 0 else '') + text[start:end] + (' …' if end < len(text) else '')
  return ''
