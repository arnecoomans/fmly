import os

from django import template

register = template.Library()


@register.filter
def visible_portrait(person, user):
  """{% with portrait=person|visible_portrait:request.user %} - the
  person's primary content.Portrait (photo + crop), only if this viewer may
  see both the person and the photo, and it's an image with a file.
  Otherwise None, and
  the avatar falls back to initials: a public person's family-only
  portrait must not show (or 404 as a broken image) for a signed-out
  visitor.

  A portrait taken from a document (e.g. a passport scan) is only used
  once its crop is set: the face is a small part of the page, and a
  center crop shows paper, not a person - worse than initials."""
  link = getattr(person, 'primary_portrait_link', None)
  if link is None:
    return None
  content = link.content
  if not content.file or content.media_type != 'image':
    return None
  if content.kind == content.Kind.DOCUMENT and link.crop_box is None:
    return None
  if not person.is_visible_to(user) or not content.is_accessible_to(user):
    return None
  return link


@register.filter
def portrait_to_crop(person, user):
  """{% if person|portrait_to_crop:request.user %} - the person's primary
  Portrait when this viewer may see both the person and the photo (an
  image), also when the avatar doesn't use it yet (a document portrait
  without a crop): edit mode's pencil, to crop it."""
  link = getattr(person, 'primary_portrait_link', None)
  if link is None or not link.content.file or link.content.media_type != 'image':
    return None
  if not person.is_visible_to(user) or not link.content.is_accessible_to(user):
    return None
  return link


# Bootstrap Icons per kind - the card's kind icon / icon chip.
_KIND_ICONS = {
  'photo': 'image',
  'document': 'file-earmark-text',
  'book': 'book',
  'object': 'gem',
  'recording': 'play-circle',
  'unknown': 'question-square',
}


@register.filter
def kind_icon(content):
  """{{ item|kind_icon }} -> a Bootstrap Icons name (without bi-). A PDF
  document gets the PDF icon; otherwise by kind."""
  if content.kind == 'document' and content.media_type == 'pdf':
    return 'file-earmark-pdf'
  return _KIND_ICONS.get(content.kind, 'file-earmark')


@register.filter
def partial_date(obj):
  """{{ item|partial_date }} -> '5-7-1968', 'ca. 1950', 'before 1950' or ''
  - PartialDateMixin.partial_date_display(): only the known parts, with
  the date qualifier."""
  display = getattr(obj, 'partial_date_display', None)
  return display() if display else ''


@register.filter
def date_sort_key(obj):
  """{{ item|date_sort_key }} -> '1943-05-00' - a text-sortable key from
  PartialDateMixin's year/month/day (unknown parts 00), '' when there's
  no year: for the "by date" sort (cmnsd.js sort.js puts '' last)."""
  if not getattr(obj, 'year', None):
    return ''
  return f"{obj.year:04d}-{getattr(obj, 'month', None) or 0:02d}-{getattr(obj, 'day', None) or 0:02d}"


LIST_SORT_KEY = 'content.list'


@register.filter
def list_sort(request):
  """{{ request|list_sort }} -> 'added' / 'date': the viewer's remembered
  order for the content list (cmnsd/ui/state.py, key 'content.list')."""
  from cmnsd.ui.state import get_sort
  return get_sort(request, LIST_SORT_KEY, 'added', ('added', 'date'))


@register.filter
def in_list_order(items, request):
  """{% with items=content_list|in_list_order:request %} - the list in the
  viewer's remembered order (list_sort): most recently added first, or
  chronologically with undated items last. Sorted here rather than in the
  query because the page and the list API (live search) render the same
  template (content/content_list.html) from a generic query."""
  items = list(items)
  if list_sort(request) == 'date':
    return sorted(items, key=lambda c: (c.year is None, c.year or 0, c.month or 0, c.day or 0, c.name.lower()))
  by_name = sorted(items, key=lambda c: c.name.lower())
  return sorted(by_name, key=lambda c: c.date_created, reverse=True)  # stable: name order within a moment


@register.filter
def mark_wholes(items, request):
  """{% for item in items|mark_wholes:request %} - what a content card
  shows about an item beyond itself, for a whole list in two queries:
  - item.has_parts / item.group_size: the whole plus the parts this viewer
    may see - the same number as the item page's Parts section (a book
    with 6 pages: 7) - the count badge;
  - item.transcript: None, or {languages, pages, incomplete} - its own
    transcripts' languages, how many of its (visible) parts have one, and
    whether any is marked incomplete - the transcript badge."""
  from collections import defaultdict
  from content.models import Content, Transcript
  from content.languages import Language
  items = list(items)
  ids = [item.pk for item in items]
  parts = defaultdict(set)   # whole -> its visible parts
  for part_id, whole_id in Content.objects.visible_to(request).filter(parent__in=ids).order_by().values_list('pk', 'parent').distinct():
    parts[whole_id].add(part_id)
  whole_of = {part_id: whole_id for whole_id, part_ids in parts.items() for part_id in part_ids}

  own = defaultdict(list)         # item -> its own transcripts' languages, original first
  transcribed_parts = defaultdict(set)
  incomplete = set()
  rows = Transcript.objects.filter(content__in=[*ids, *whole_of]).values_list('content_id', 'language', 'incomplete')
  for content_id, language, is_incomplete in rows:
    item_id = whole_of.get(content_id, content_id)
    if content_id in whole_of:
      transcribed_parts[item_id].add(content_id)
    elif language not in own[item_id]:
      own[item_id].append(language)   # in Transcript's order: the original first
    if is_incomplete:
      incomplete.add(item_id)

  labels = dict(Language.choices)
  for item in items:
    count = len(parts.get(item.pk, ()))
    item.has_parts = bool(count)
    item.group_size = count + 1 if count else 0
    if own.get(item.pk) or transcribed_parts.get(item.pk):
      item.transcript = {
        'languages': [str(labels.get(code, code)) for code in own.get(item.pk, ())],
        'pages': len(transcribed_parts.get(item.pk, ())),
        'incomplete': item.pk in incomplete,
      }
    else:
      item.transcript = None
  return items


@register.filter
def portrait_from(person, content):
  """{{ person|portrait_from:content }} - whether this photo is the
  person's portrait (their primary Portrait). Uses the batch-attached link
  when a list attached one (Person._attach_portraits), so a row costs no
  query."""
  link = person.primary_portrait_link
  return bool(link and link.content_id == content.pk)


@register.filter
def portrait_choosable(person, request):
  """{% if person|portrait_choosable:request %} - edit mode's avatar pencil:
  there's a portrait to crop, or an image the person is tagged in to make
  one of (content/portraits.py portrait_candidates)."""
  from content.portraits import portrait_candidates
  return bool(portrait_to_crop(person, request.user) or portrait_candidates(person, request))


@register.filter
def inbox_count(user):
  """{{ request.user|inbox_count }} - how many drafts the user has in their
  inbox: content, people and events (content/views/upload.py inbox_total)."""
  from content.views.upload import inbox_total
  return inbox_total(user)


@register.filter
def thumb_url(content, preset):
  """{{ item|thumb_url:'card' }} - the item's thumbnail in a named size
  (content:thumbnail), with ?v= from its own crop (Content.thumb_version)
  when it has one: a changed crop is a new address, so a browser doesn't
  keep showing the previous one."""
  from django.urls import reverse
  url = reverse('content:thumbnail', args=[content.token, preset])
  version = content.thumb_version
  return f'{url}?v={version}' if version else url


@register.filter
def file_info(content):
  """{{ content|file_info }} -> 'JPEG · 4800 × 3600 px · 12.4 MB' - the
  file's format, an image's size as shown (Content.width/height) and the
  size on disk (read now, never stale). '' without a file; a part that
  can't be read is left out."""
  from django.template.defaultfilters import filesizeformat
  if not content.file:
    return ''
  parts = []
  extension = os.path.splitext(content.file.name)[1].lstrip('.').upper()
  if extension:
    parts.append({'JPEG': 'JPEG', 'JPG': 'JPEG', 'TIF': 'TIFF'}.get(extension, extension))
  if content.width and content.height:
    parts.append(f'{content.width} × {content.height} px')
  try:
    parts.append(str(filesizeformat(content.file.size)))
  except (OSError, ValueError):
    pass
  return ' · '.join(parts)
