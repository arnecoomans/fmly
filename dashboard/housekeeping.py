"""
Housekeeping (/dashboard/housekeeping/, dashboard.views.HousekeepingView):
the archive's storage, checked by eye - for staff who may delete content.

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
from django.db.models import Count
from django.utils.translation import ngettext


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
  a place (alternatives): Djakarta matters as Batavia's later name."""
  from places.models import Place
  return list(
    Place.objects.filter(content__isnull=True, events__isnull=True, notes__isnull=True, children__isnull=True, alternatives__isnull=True)
    .select_related('parent', 'user').distinct().order_by('name')
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

