"""
Housekeeping (/dashboard/housekeeping/, dashboard.views.HousekeepingView):
the archive's storage, checked by eye - for staff who may delete content.
An overview of counts in groups (SECTIONS), each section a page of
its own (/dashboard/housekeeping/<section>/).

- revoked, to review: people, content, events and notes pulled back by
  staff, by kind, with the discussion -
  every revocation reason (a titled comment) and what was said since -
  republished or deleted on their page.

- deleted items: content with status "deleted" (hidden from everyone, but
  record and file still there) - purge: the record, its file and its
  thumbnails, for good. Its parts go with it, so an item with parts that
  aren't deleted themselves can't be purged.
- files without a record: files under MEDIA_ROOT/content/ no item points
  to (an old name, an abandoned upload) - delete the file.
- same file twice: items with the same checksum, side by side - delete
  the unwanted one on its page (soft), then purge it here, from its pair.
  A file another item uses as well (the same stored name) is kept.
- records without a file: items whose file is empty or gone - listed, fixed
  on their page.
- unused tags and places (issue #460): nothing carries or lies in them - a
  tag without content, people, notes or tags under it; a place without
  content, events, notes, places in it or a name in another era. FMLY 2's
  old categories, a typo, something abandoned - or something meant for
  later (Nieuw Guinea, for the history to come): hence by eye, not in
  .post_update.sh. The "Loose end" tag is never offered.
- linked twice (records): a person linked to an item that documents an
  event they took part in - the event shows it on their page already;
  remove the direct link where it adds nothing.

The hard deletes are purging what's deleted already, removing files nothing
points to, and unused tags and places; each goes through a confirmation
that lists exactly what goes. Each purge is logged (LogEntry). There is no undo but a backup.
"""

import os
from collections import defaultdict
from pathlib import Path

from django.conf import settings
from django.contrib.admin.models import DELETION, LogEntry
from django.core.files.storage import default_storage
from django.db.models import Count, F, Q
from django.utils.translation import gettext_lazy, ngettext


def _plural(singular, plural):
  """A count phrase: _plural("%(n)s part", "%(n)s parts")(n) % {"n": n}."""
  return lambda n: ngettext(singular, plural, n)

CONTENT_DIR = 'content'


def may_housekeep(user):
  return bool(user and user.is_authenticated and user.is_staff and user.has_perm('content.delete_content'))


def _content_root():
  return (Path(settings.MEDIA_ROOT) / CONTENT_DIR).resolve()


def stored_names():
  """Every file name an item points to, whatever its status."""
  from content.models import Content
  return set(Content.objects.exclude(file='').values_list('file', flat=True))


def is_image_name(name):
  return os.path.splitext(name)[1].lower() in ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.tif', '.tiff', '.bmp')


def safe_name(name):
  """A storage name under content/ that really lies there (no ../), or None."""
  if not name or not name.startswith(f'{CONTENT_DIR}/'):
    return None
  path = (Path(settings.MEDIA_ROOT) / name).resolve()
  root = _content_root()
  if root not in path.parents or not path.is_file():
    return None
  return name


def files_without_record():
  """[{name, size, image}] - files under content/ no item points to, by name."""
  root = _content_root()
  if not root.is_dir():
    return []
  known = stored_names()
  media = Path(settings.MEDIA_ROOT).resolve()
  found = []
  for directory, _dirs, files in os.walk(root):
    for filename in files:
      if filename.startswith('.'):
        continue
      path = Path(directory) / filename
      name = path.relative_to(media).as_posix()
      if name not in known:
        found.append({'name': name, 'size': path.stat().st_size, 'image': is_image_name(name)})
  return sorted(found, key=lambda f: f['name'])


def records_without_file():
  """Items whose file is empty or not on disk, any status."""
  from content.models import Content
  missing = []
  for item in Content.objects.order_by('name', 'pk'):
    if not item.file or not default_storage.exists(item.file.name):
      missing.append(item)
  return missing


def same_file_twice():
  """[[Content]] - items sharing a checksum, each group by status (published
  first) and date."""
  from content.models import Content
  checksums = (
    Content.objects.exclude(checksum='').values('checksum')
    .annotate(n=Count('pk')).filter(n__gt=1).values_list('checksum', flat=True)
  )
  groups = defaultdict(list)
  for item in Content.objects.filter(checksum__in=list(checksums)).order_by('status', 'date_created'):
    groups[item.checksum].append(item)
  result = list(groups.values())
  for items in result:
    attach_consequences(items)
  return result


def deleted_items():
  from content.models import Content
  items = list(Content.objects.filter(status=Content.Status.DELETED).order_by('-date_modified'))
  attach_consequences(items)
  return items


def attach_consequences(items):
  """On each item: what hangs on it (parts, transcripts, comments,
  portraits, people, notes) and `blocked` - why it can't be purged, or ''."""
  from content.models import Content
  for item in items:
    item.purge_parts = list(item.parts.all())
    counts = (
      (len(item.purge_parts), _plural("%(n)s part", "%(n)s parts")),
      (item.transcripts.count() + sum(part.transcripts.count() for part in item.purge_parts), _plural("%(n)s transcript", "%(n)s transcripts")),
      (item.comments.count(), _plural("%(n)s comment", "%(n)s comments")),
      (item.portrait_links.count(), _plural("%(n)s portrait", "%(n)s portraits")),
      (item.people.count(), _plural("%(n)s person", "%(n)s people")),
      (item.notes.count(), _plural("%(n)s note", "%(n)s notes")),
    )
    # What goes with it (or is unlinked), for the page: '1 part · 2 comments'.
    item.purge_summary = ' · '.join(str(words(n) % {'n': n}) for n, words in counts if n)
    live_parts = [part for part in item.purge_parts if part.status != Content.Status.DELETED]
    item.blocked = 'parts' if live_parts else ''
    # The very same stored file used by another item: purging keeps it.
    own = [item.pk, *(part.pk for part in item.purge_parts)]
    item.file_shared = bool(item.file) and Content.objects.filter(file=item.file.name).exclude(pk__in=own).exists()
  return items


def _shared(obj, purging):
  """Whether another item, not being purged with it, uses obj's file."""
  from content.models import Content
  return Content.objects.filter(file=obj.file.name).exclude(pk__in=purging).exists()


def _delete_file(field_file):
  """The file and its thumbnails (sorl: cache files and key-value entries)."""
  if not field_file:
    return
  from sorl.thumbnail import delete as delete_thumbnails
  try:
    delete_thumbnails(field_file, delete_file=True)
  except Exception:
    # Thumbnails or not, the file itself goes.
    if default_storage.exists(field_file.name):
      default_storage.delete(field_file.name)


def purge(items, user):
  """Hard-delete deleted items (and their parts): files, thumbnails,
  records. Returns how many records went. Skips anything not deleted or
  blocked - checked again here, not trusted from the form."""
  from content.models import Content
  gone = 0
  for item in attach_consequences([i for i in items if i.status == Content.Status.DELETED]):
    if item.blocked:
      continue
    LogEntry.objects.log_actions(
      user.pk, [item, *item.purge_parts], DELETION,
      change_message=f"Purged in housekeeping (file {item.file.name or '-'})",
    )
    purging = [item.pk, *(part.pk for part in item.purge_parts)]
    for obj in [*item.purge_parts, item]:
      if obj.file and not _shared(obj, purging):
        _delete_file(obj.file)
    gone += 1 + len(item.purge_parts)
    for part in item.purge_parts:
      part.delete()
    item.delete()
  return gone


def delete_files(names):
  """Remove files nothing points to - each checked again: under content/,
  there, and still without a record. Returns how many went."""
  known = stored_names()
  gone = 0
  for name in names:
    name = safe_name(name)
    if name is None or name in known:
      continue
    default_storage.delete(name)
    gone += 1
  return gone


def unused_tags():
  """Tags nothing carries and nothing sits under - not the "Loose end" tag
  (core.tags: found by its slug, used now and then)."""
  from core.models import Tag
  from core.tags import LOOSE_END_SLUG
  return list(
    Tag.objects.filter(content__isnull=True, people__isnull=True, notes__isnull=True, children__isnull=True)
    .exclude(slug=LOOSE_END_SLUG, parent=None).select_related('parent', 'user').distinct().order_by('name')
  )


def unused_places():
  """Places nothing lies in or happened at - also not another era's name of
  a place (alternatives): Djakarta matters as Batavia's later name - and not
  mentioned in any text: deleting it would leave that link leading nowhere."""
  from django.contrib.contenttypes.models import ContentType
  from cmnsd.models import Mention
  from places.models import Place
  mentioned = Mention.objects.filter(target_content_type=ContentType.objects.get_for_model(Place)).values('target_id')
  return list(
    Place.objects.filter(content__isnull=True, events__isnull=True, notes__isnull=True, children__isnull=True, alternatives__isnull=True)
    .exclude(pk__in=mentioned).select_related('parent', 'user').distinct().order_by('name')
  )


def may_delete(user, kind):
  return may_housekeep(user) and user.has_perm({'tags': 'core.delete_tag', 'places': 'places.delete_place'}[kind])


def selected_unused(kind, tokens):
  """The selection, as far as still unused - checked again at the moment
  of deleting: something linked in between stays."""
  unused = unused_tags() if kind == 'tags' else unused_places()
  return [obj for obj in unused if obj.token in set(tokens)]


def delete_unused(objects, user):
  """Delete, each in the admin log. Returns how many."""
  for obj in objects:
    LogEntry.objects.log_actions(user.pk, [obj], DELETION, change_message="Deleted in housekeeping (unused)", single_object=True)
    obj.delete()
  return len(objects)


def revoked_items():
  """Everything under review: revoked people, content, events and notes -
  by kind, newest first within each (`review_kind`: the kind's name, for
  the page's headings). Each with its discussion (`discussion`: every
  comment on it, oldest first - the revocation reasons, titled, made when
  it was revoked (core.forms StatusActionsForm), and what was said about
  them), so the case can be read here before opening it. A note has no
  comments: no discussion. Deleted comments left out; hidden ones shown -
  this is for staff. One query per kind, and one for the comments."""
  from content.models import Content
  from core.models import Comment
  from django.contrib.contenttypes.models import ContentType
  from events.models import Event
  from notes.models import Note
  from people.models import Person
  items = []
  for model in (Person, Content, Event, Note):
    found = list(model.objects.filter(status=model.Status.REVOKED).order_by('-date_modified'))
    for item in found:
      item.review_kind = model._meta.verbose_name_plural
      item.is_content = model is Content          # its own row: preview, kind, file
      item.has_discussion = hasattr(model, 'comments')
      item.discussion = []
    items += found
  wanted = None
  for model in {type(item) for item in items}:
    if hasattr(model, 'comments'):
      query = Q(target_content_type=ContentType.objects.get_for_model(model), target_id__in=[i.pk for i in items if type(i) is model])
      wanted = query if wanted is None else wanted | query
  if wanted is not None:
    discussion = defaultdict(list)
    for comment in Comment.objects.filter(wanted).exclude(status=Comment.Status.DELETED).select_related('user').order_by('date_created'):
      discussion[(comment.target_content_type_id, comment.target_id)].append(comment)
    for item in items:
      item.discussion = discussion[(ContentType.objects.get_for_model(item).pk, item.pk)]
  return items


def life_event_conflicts():
  """Births and deaths that break the rule (events.models.life_event_problem):
  someone with two births or two deaths - the second is invisible, every
  view takes "the" one - and a birth or death of several people (twins:
  one each). From before the rule; normally none. Not deleted ones.
  [{'kind', 'person' or 'event', 'events'}]."""
  from django.db.models import Count
  from events.models import Event, LIFE_KINDS
  from people.models import Person
  rows = []
  for kind in LIFE_KINDS:
    doubled = Person.objects.filter(events__kind=kind, events__status__in=('c', 'p', 'r')).annotate(n=Count('events', distinct=True)).filter(n__gt=1)
    for person in doubled:
      events = list(Event.objects.current().filter(kind=kind, people=person).prefetch_related('places'))
      if len(events) > 1:
        rows.append({'kind': 'twice', 'label': Event.Kind(kind).label, 'person': person, 'events': events})
    for event in Event.objects.current().filter(kind=kind).annotate(n=Count('people')).filter(n__gt=1).prefetch_related('people'):
      rows.append({'kind': 'shared', 'label': Event.Kind(kind).label, 'event': event, 'people': list(event.people.all())})
  return rows


def linked_twice():
  """People linked to an item that also documents an event they took part
  in - the same thing administered twice: the event already brings the
  item to their page (related content, "via marriage 1889"). Only where the
  direct link adds nothing: no role, or subject (a record of that moment);
  no frame; not a photo - who's on a photo is more than who was there.
  Not historical events (they aren't anyone's own), nothing deleted. By
  eye, one at a time - suggest, never auto-set: a link removed here is
  the item's "×". Per item its events, each with who took part and who of
  them is linked directly too (under the first such event only, so a link
  is listed once): [{'content', 'events': [{'event', 'people', 'direct':
  [{'person', 'role'}]}]}], by item name."""
  from content.models import Content, ContentPerson
  from events.models import Event
  links = list(
    ContentPerson.objects.filter(
      role__in=('', ContentPerson.Role.SUBJECT), region_x__isnull=True,
      content__events__people=F('person'),
    ).exclude(content__kind=Content.Kind.PHOTO).exclude(content__status=Content.Status.DELETED)
    .select_related('content', 'person').distinct().order_by('content__name', 'content__pk', 'person__pk')
  )
  events_of = defaultdict(list)
  events = (
    Event.objects.current().exclude(kind=Event.Kind.HISTORICAL)
    .filter(content__in={link.content_id for link in links}).distinct()
    .prefetch_related('people', 'content', 'places').order_by('year', 'month', 'day', 'pk')
  )
  for event in events:
    for item in event.content.all():
      events_of[item.pk].append(event)
  groups = {}
  for link in links:
    shared = [event for event in events_of[link.content_id] if link.person in event.people.all()]
    if not shared:
      continue
    group = groups.setdefault(link.content_id, {'content': link.content, 'events': {}})
    row = group['events'].setdefault(shared[0].pk, {'event': shared[0], 'people': list(shared[0].people.all()), 'direct': []})
    row['direct'].append({'person': link.person, 'role': link.role})
  for group in groups.values():
    group['events'] = list(group['events'].values())
  return list(groups.values())


def broken_mentions():
  """Mentions that lead nowhere (cmnsd mention_problems): gone, revoked or
  deleted - remove the link (the words stay), or restore the target."""
  from cmnsd.models.Mention import mention_problems
  return mention_problems()


# The overview's groups and their sections: (group label, [(section, label,
# context name, its list)]). A section page renders housekeeping/<section>.html
# with its list under that context name.
SECTIONS = (
  (gettext_lazy("to review"), (
    ('revoked', gettext_lazy("revoked, to review"), 'revoked', revoked_items),
    ('deleted', gettext_lazy("deleted items, to purge"), 'deleted', deleted_items),
  )),
  (gettext_lazy("files"), (
    ('duplicates', gettext_lazy("same file twice"), 'duplicates', same_file_twice),
    ('orphans', gettext_lazy("files without a record"), 'orphans', files_without_record),
    ('missing', gettext_lazy("records without a file"), 'missing', records_without_file),
  )),
  (gettext_lazy("tags and places"), (
    ('unused-tags', gettext_lazy("unused tags"), 'unused_tags', unused_tags),
    ('unused-places', gettext_lazy("unused places"), 'unused_places', unused_places),
  )),
  (gettext_lazy("records"), (
    ('life-events', gettext_lazy("births and deaths that break the rules"), 'conflicts', life_event_conflicts),
    ('linked-twice', gettext_lazy("people linked twice"), 'linked_twice', linked_twice),
  )),
  (gettext_lazy("texts"), (
    ('mentions', gettext_lazy("mentions that lead nowhere"), 'mentions', broken_mentions),
  )),
)
SECTION_BY_NAME = {name: (label, context, find) for _group, sections in SECTIONS for name, label, context, find in sections}


def overview():
  """[(group label, [(section, label, count)])] - for the overview page."""
  return [(group, [(name, label, len(find())) for name, label, _context, find in sections]) for group, sections in SECTIONS]

