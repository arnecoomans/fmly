"""
Links between legacy records that are imported by different commands.

A link needs both sides to exist, and a development reload can run the
importers in any order - so every importer that brings in one side calls
the link function too, and whichever runs last completes the set. Links
are only ever added, never removed: a link made by hand on the site
survives a re-import.
"""

import json
import re
from pathlib import Path


def link_event_images(fixtures):
  """archive_event.images -> Content.events. Event and image pks are kept
  on import (import_events, import_content), so the legacy pks map
  directly. Returns (linked, waiting): links present now, and legacy links
  whose event or content doesn't exist (yet)."""
  from content.models import Content
  from events.models import Event

  rows = json.loads((Path(fixtures) / 'archive_event.json').read_text())
  pairs = [(row['pk'], image) for row in rows for image in row['fields'].get('images', [])]
  events = set(Event.objects.filter(pk__in={e for e, _ in pairs}).values_list('pk', flat=True))
  contents = {c.pk: c for c in Content.objects.filter(pk__in={i for _, i in pairs})}

  linked = waiting = 0
  for event_pk, image_pk in pairs:
    content = contents.get(image_pk)
    if event_pk in events and content is not None:
      content.events.add(event_pk)
      linked += 1
    else:
      waiting += 1
  return linked, waiting


# A link to the old site: absolute (https://fmly.cmns.nl/person/59/...) or,
# as a Markdown link target, site-relative (](/person/59/...)).
OLD_SITE_LINK = re.compile(r'(?:https?://fmly\.cmns\.nl|(?<=\]\())/(person|persoon|image|object)/([^/\s)\]]+)/?[^\s)\]]*')


def rewrite_old_links(text):
  """Links to the old site -> the new pages (site-relative): person/
  persoon/<pk>/... -> that person, image/<pk>/... -> that content item
  (pks kept on import), object/<slug>/ -> the person with that slug.
  A link whose target doesn't exist here (or has no page, e.g. a private
  person) is left as it was. Returns (text, how many were rewritten)."""
  from content.models import Content
  from people.models import Person
  rewritten = 0

  def replace(match):
    nonlocal rewritten
    section, key = match.groups()
    target = None
    if section in ('person', 'persoon') and key.isdigit():
      target = Person.objects.filter(pk=int(key)).first()
    elif section == 'image' and key.isdigit():
      target = Content.objects.filter(pk=int(key)).first()
    elif section == 'object':
      target = Person.objects.filter(slug=key).first()
    url = target.get_absolute_url() if target else None
    if not url:
      return match.group(0)
    rewritten += 1
    return url

  return OLD_SITE_LINK.sub(replace, text or ''), rewritten
