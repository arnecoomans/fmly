import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from events.models import Event
from legacy_import.links import link_event_images
from legacy_import.sequences import reset_sequences

# 5 old 'other'-type rows (pks 278-282) have no title, no description and no
# people - only a location - so there's nothing to derive a kind_freetext
# from (required by Event.clean() when kind='other'). Decision: import these
# as HISTORICAL instead of OTHER rather than fabricate a label.
OTHER_WITHOUT_LABEL_AS_HISTORICAL = {278, 279, 280, 281, 282}

# Old type -> new kind where the name changed: 'general' (events without
# people - the Japanese invasion, the transfer of sovereignty) is now
# HISTORICAL.
RENAMED_KINDS = {'general': 'historical'}


class Command(BaseCommand):
  help = (
    "Import events from import/fixtures/archive_event.json (a raw dumpdata "
    "export from the old environment). type -> kind is a direct rename "
    "(birth/death/marriage/other unchanged, general -> historical: "
    "RENAMED_KINDS); 29 of 34 'other' rows have a title, reused as "
    "kind_freetext (required by Event.clean() when kind='other') - the "
    "remaining 5 (see OTHER_WITHOUT_LABEL_AS_HISTORICAL) are imported as "
    "HISTORICAL instead, per explicit decision, rather than fabricate a label "
    "that isn't in the source. images (14 rows) has no home on the new "
    "Event yet - deferred to a future Content import, left untouched in "
    "the fixture, not lost. 65 of 388 rows have no user set in the source "
    "(same gap as import_places) - Event.user is NOT NULL, and every row "
    "that does have a user is 1, so these default to user 1 too."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      '--path', default=None,
      help="Path to the fixture (default: import/fixtures/archive_event.json)",
    )

  def handle(self, *args, **options):
    path = Path(options['path']) if options['path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_event.json'
    rows = json.loads(path.read_text())

    created, updated, recast_as_historical = 0, 0, 0

    for row in rows:
      f = row['fields']
      pk = row['pk']

      kind = RENAMED_KINDS.get(f['type'], f['type'])
      kind_freetext = ''
      if kind == Event.Kind.OTHER:
        if pk in OTHER_WITHOUT_LABEL_AS_HISTORICAL:
          kind = Event.Kind.HISTORICAL
          recast_as_historical += 1
        else:
          kind_freetext = f.get('title') or ''

      obj, was_created = Event.objects.update_or_create(
        pk=pk,
        defaults={
          'token': f.get('token', ''),
          'kind': kind,
          'kind_freetext': kind_freetext,
          'title': f.get('title') or '',
          'description': f.get('description') or '',
          'year': f.get('year'),
          'month': f.get('month'),
          'day': f.get('day'),
          'user_id': f.get('user') or 1,
        },
      )
      if was_created:
        created += 1
      else:
        updated += 1

      obj.people.set(f.get('people', []))
      obj.places.set(f.get('locations', []))

      Event.objects.filter(pk=obj.pk).update(
        date_created=parse_datetime(f['date_created']),
        date_modified=parse_datetime(f['date_modified']),
      )

    # Event <-> content links (archive_event.images). Also done by
    # import_content - whichever of the two runs last completes the set.
    linked, waiting = link_event_images(Path(settings.BASE_DIR) / 'import' / 'fixtures')

    reset_sequences()   # PostgreSQL: new rows get ids after the imported ones (legacy_import/sequences.py)
    self.stdout.write(self.style.SUCCESS(
      f"Events: {created} created, {updated} updated, {len(rows)} total "
      f"({recast_as_historical} 'other'-without-label row(s) imported as HISTORICAL); "
      f"{linked} content links, {waiting} waiting for content (run import_content)."
    ))
