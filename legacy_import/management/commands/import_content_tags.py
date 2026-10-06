import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from core.models import Tag
from legacy_import.pk_offsets import CATEGORY_TAG_PK_OFFSET
from legacy_import.tag_layout import IMPORTED_TAG_ACCESS, tag_layout
from legacy_import.sequences import reset_sequences


class Command(BaseCommand):
  help = (
    "Import tags from import/fixtures/archive_tag.json (30 rows) and "
    "archive_category.json (8 rows) into core.Tag - both are flat "
    "name/slug/parent taxonomies with no home of their own in the new "
    "architecture (Category was explicitly parked earlier in favor of "
    "Kind; this data doesn't actually classify file type, it sub-classifies "
    "photo content, so it fits as tags instead). "
    "archive_tag and archive_category old pk ranges overlap (both start at "
    "1), so category rows are imported at pk = old_pk + "
    f"{CATEGORY_TAG_PK_OFFSET} (see legacy_import/pk_offsets.py) - a later "
    "photo importer resolving Image.category by old pk must apply the same "
    "offset. Category's icon has no home on Tag - dropped, nothing lost. "
    "archive.group (26 rows, image albums, not a topical taxonomy) is "
    "deliberately NOT imported here - 2 of its titles slugify to the same "
    "slug as an unrelated existing tag ('medan', 'boot'), and its own "
    "'tag' field turns out to mostly be a shared 'ingekleurd' (colorized) "
    "marker applied across unrelated groups, not a name correspondence - "
    "merging it into Tag risks conflating two different concepts. Left for "
    "a decision when the photo importer (which needs Image.in_group) is "
    "built."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      '--tag-path', default=None,
      help="Path to archive_tag.json (default: import/fixtures/archive_tag.json)",
    )
    parser.add_argument(
      '--category-path', default=None,
      help="Path to archive_category.json (default: import/fixtures/archive_category.json)",
    )

  def handle(self, *args, **options):
    tag_path = Path(options['tag_path']) if options['tag_path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_tag.json'
    category_path = Path(options['category_path']) if options['category_path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_category.json'

    tag_rows = json.loads(tag_path.read_text())
    category_rows = json.loads(category_path.read_text())

    created, updated = 0, 0

    # Pass 1: tags (no parent usage in the source at all) and categories
    # (parent left out of defaults - deferred to pass 2, same reasoning as
    # import_places: avoids any FK-ordering assumption).
    # Renamed where decided (legacy_import/tag_layout.py); a collection's
    # parent ("Collection") is set after all rows are in: made now, that
    # root tag would take the next free pk - a legacy tag's, which
    # update_or_create(pk=...) then overwrites, leaving that tag its own parent.
    for row in tag_rows:
      f = row['fields']
      name, _parent = tag_layout(f.get('slug', ''), f.get('name', ''), defer_parent=True)
      obj, was_created = Tag.objects.update_or_create(
        pk=row['pk'],
        defaults={
          'token': f.get('token', ''),
          'name': name,
          'slug': f.get('slug', ''),
          'description': f.get('description', ''),
          'user_id': f.get('user') or 1,
          **IMPORTED_TAG_ACCESS,   # published, visibility community
        },
      )
      created += was_created
      updated += not was_created
      Tag.objects.filter(pk=obj.pk).update(
        date_created=parse_datetime(f['date_created']),
        date_modified=parse_datetime(f['date_modified']),
      )

    # The root tags below are new rows without a pk: PostgreSQL's next id must
    # be past the tags just imported (legacy_import/sequences.py).
    reset_sequences(Tag)
    for row in tag_rows:
      _name, parent = tag_layout(row['fields'].get('slug', ''), row['fields'].get('name', ''))
      Tag.objects.filter(pk=row['pk']).update(parent=parent)

    for row in category_rows:
      f = row['fields']
      pk = row['pk'] + CATEGORY_TAG_PK_OFFSET
      obj, was_created = Tag.objects.update_or_create(
        pk=pk,
        defaults={
          'token': f.get('token', ''),
          'name': f.get('name', ''),
          'slug': f.get('slug', ''),
          'description': '',
          'user_id': f.get('user') or 1,
          **IMPORTED_TAG_ACCESS,   # published, visibility community
        },
      )
      created += was_created
      updated += not was_created
      Tag.objects.filter(pk=obj.pk).update(
        date_created=parse_datetime(f['date_created']),
        date_modified=parse_datetime(f['date_modified']),
      )

    # Pass 2: category parent (the only source of parent data here).
    for row in category_rows:
      parent_pk = row['fields'].get('parent')
      if parent_pk is not None:
        Tag.objects.filter(pk=row['pk'] + CATEGORY_TAG_PK_OFFSET).update(
          parent_id=parent_pk + CATEGORY_TAG_PK_OFFSET,
        )

    reset_sequences()   # PostgreSQL: new rows get ids after the imported ones (legacy_import/sequences.py)
    self.stdout.write(self.style.SUCCESS(
      f"Tags: {created} created, {updated} updated, "
      f"{len(tag_rows) + len(category_rows)} total "
      f"({len(tag_rows)} from archive_tag, {len(category_rows)} from "
      f"archive_category at pk+{CATEGORY_TAG_PK_OFFSET})."
    ))
