import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from places.models import Place
from legacy_import.sequences import reset_sequences


class Command(BaseCommand):
  help = (
    "Import places from import/fixtures/archive_location.json (a raw "
    "dumpdata export from the old environment). Old status/icon have no "
    "home on the new Place (it composes no StatusMixin, and icon is empty "
    "on every row anyway) - dropped, nothing lost. coord_lat/coord_lon "
    "rename to latitude/longitude (all null in the source data). "
    "Runs in three passes: (1) create every row with parent left unset - "
    "71 of the 132 parent references point to a row that appears LATER in "
    "the file / has a HIGHER pk, so a single-pass update_or_create would "
    "hit FK errors; (2) a raw queryset .update(parent_id=...) per row, "
    "bypassing save() (so _split_compounded_name() never runs - confirmed "
    "no name contains the parent/child compounder anyway, but this is "
    "correct either way and sidesteps all ordering concerns); "
    "(3) .add() the (symmetric) alternatives M2M once all rows exist. "
    "3 of 161 rows have no user set in the source (Sulawesi/Utrecht "
    "Provincie/Quebec) - Place.user is NOT NULL (OwnershipMixin has no "
    "field default by design), and 158/161 rows already belong to user 1, "
    "so these 3 default to user 1 too rather than fail the import."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      '--path', default=None,
      help="Path to the fixture (default: import/fixtures/archive_location.json)",
    )

  def handle(self, *args, **options):
    path = Path(options['path']) if options['path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_location.json'
    rows = json.loads(path.read_text())

    created, updated = 0, 0

    # Pass 1: create/update every row, parent deliberately left out of
    # defaults so it's never touched by save()'s compound-name split.
    for row in rows:
      f = row['fields']
      obj, was_created = Place.objects.update_or_create(
        pk=row['pk'],
        defaults={
          'token': f.get('token', ''),
          'name': f.get('name', ''),
          'description': f.get('description', ''),
          'latitude': f.get('coord_lat'),
          'longitude': f.get('coord_lon'),
          'user_id': f.get('user') or 1,
        },
      )
      if was_created:
        created += 1
      else:
        updated += 1

      Place.objects.filter(pk=obj.pk).update(
        date_created=parse_datetime(f['date_created']),
        date_modified=parse_datetime(f['date_modified']),
      )

    # Pass 2: wire up parent - all pks now exist, so ordering no longer matters.
    for row in rows:
      parent_pk = row['fields'].get('parent')
      if parent_pk is not None:
        Place.objects.filter(pk=row['pk']).update(parent_id=parent_pk)

    # Pass 3: alternatives (symmetric M2M) - add one direction per pair only.
    alt_pairs_added = 0
    seen_pairs = set()
    for row in rows:
      alt_pks = row['fields'].get('alternatives') or []
      for alt_pk in alt_pks:
        pair = frozenset((row['pk'], alt_pk))
        if pair in seen_pairs:
          continue
        seen_pairs.add(pair)
        Place.objects.get(pk=row['pk']).alternatives.add(alt_pk)
        alt_pairs_added += 1

    reset_sequences()   # PostgreSQL: new rows get ids after the imported ones (legacy_import/sequences.py)
    self.stdout.write(self.style.SUCCESS(
      f"Places: {created} created, {updated} updated, {len(rows)} total "
      f"({alt_pairs_added} alternative-pair link(s) added)."
    ))
