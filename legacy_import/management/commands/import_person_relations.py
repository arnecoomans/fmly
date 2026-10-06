import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from people.models import PersonRelation
from legacy_import.sequences import reset_sequences


class Command(BaseCommand):
  help = (
    "Import family relations from import/fixtures/archive_familyrelations.json "
    "(a raw dumpdata export from the old environment). Just a field rename "
    "(up/down/type -> person_from/person_to/relation_type, same values) - "
    "no timestamp fields to preserve (PersonRelation composes no cmnsd "
    "mixins). Uses update_or_create(pk=...) rather than a natural-key "
    "lookup so re-running stays idempotent even though PersonRelation.save() "
    "reorders PARTNER pairs canonically - a lookup by the old up/down order "
    "could otherwise miss an already-canonicalized row on a second run."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      '--path', default=None,
      help="Path to the fixture (default: import/fixtures/archive_familyrelations.json)",
    )

  def handle(self, *args, **options):
    path = Path(options['path']) if options['path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_familyrelations.json'
    rows = json.loads(path.read_text())

    created, updated = 0, 0

    for row in rows:
      f = row['fields']
      obj, was_created = PersonRelation.objects.update_or_create(
        pk=row['pk'],
        defaults={
          'person_from_id': f['up'],
          'person_to_id': f['down'],
          'relation_type': f['type'],
        },
      )
      if was_created:
        created += 1
      else:
        updated += 1

    reset_sequences()   # PostgreSQL: new rows get ids after the imported ones (legacy_import/sequences.py)
    self.stdout.write(self.style.SUCCESS(
      f"Person relations: {created} created, {updated} updated, {len(rows)} total."
    ))
