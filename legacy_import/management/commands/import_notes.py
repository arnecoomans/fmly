import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from legacy_import.links import rewrite_old_links
from notes.models import Note

# What each legacy note is (Note.Kind) - decided per note, by its legacy pk
# (only to look it up here - the note itself gets a new pk);
# the old site had no kinds. Anything not listed is context. Change a kind
# on the note's page afterwards; a re-import keeps that choice.
KINDS = {
  1: Note.Kind.CONTEXT,      # Welkom op fmly.cmns.nl - about the site
  2: Note.Kind.SCRATCH,      # Linkdump - sources to look at
  3: Note.Kind.CONTEXT,      # Het leven in Medan (1946-1950)
  4: Note.Kind.CONTEXT,      # Bijzondere Bronvermelding - frequent sources
  5: Note.Kind.CONTEXT,      # Nederlands Patriciaat - a source, excerpted
  6: Note.Kind.TODO,         # Persoons-info uit te zoeken
  7: Note.Kind.QUESTION,     # Onze Indische Historie [Werkdocument] - who went to the Indies when
  8: Note.Kind.CONTEXT,      # Artillerie Constructie Winkel Soerabaja / Bandoeng - a timeline
}


class Command(BaseCommand):
  help = (
    "Import notes from import/fixtures/archive_note.json (8 rows) into "
    "notes.Note, matched by the legacy token (kept) - not by pk: notes are "
    "made on the site too, so a legacy pk may be taken. Title, text (Markdown, old-site "
    "links rewritten to the new pages - legacy_import/links.py), author, "
    "dates. Published, visible to signed-in users (community) - they were "
    "shared on the old site. Kind per note from KINDS (the old site had "
    "none). People and tags linked (their pks are kept on import); links "
    "are only added, never removed. images and attachments are empty in "
    "the fixture. Idempotent: a re-import updates text and dates but keeps "
    "a kind, status or visibility changed on the site."
  )

  def add_arguments(self, parser):
    parser.add_argument('--path', default=None, help="Path to archive_note.json (default: import/fixtures/archive_note.json)")

  def handle(self, *args, **options):
    from core.models import Tag
    from people.models import Person
    path = Path(options['path']) if options['path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_note.json'
    rows = json.loads(path.read_text())
    created = updated = rewritten = people = tags = 0

    for row in rows:
      f = row['fields']
      body, count = rewrite_old_links(f.get('content', ''))
      rewritten += count
      note, was_created = Note.objects.update_or_create(
        token=f['token'],
        defaults={'title': f.get('title', '').strip(), 'body': body, 'user_id': f.get('user') or 1},
        create_defaults={
          'title': f.get('title', '').strip(), 'body': body, 'user_id': f.get('user') or 1,
          'kind': KINDS.get(row['pk'], Note.Kind.CONTEXT),
          'status': Note.Status.PUBLISHED if f.get('status') == 'p' else Note.Status.CONCEPT,
          'visibility': Note.Visibility.COMMUNITY,
        },
      )
      created += was_created
      updated += not was_created
      found_people = Person.objects.filter(pk__in=f.get('people', []))
      found_tags = Tag.objects.filter(pk__in=f.get('tags', []))
      note.people.add(*found_people)
      note.tags.add(*found_tags)
      people += found_people.count()
      tags += found_tags.count()
      Note.objects.filter(pk=note.pk).update(
        date_created=parse_datetime(f['date_created']), date_modified=parse_datetime(f['date_modified']),
      )

    self.stdout.write(self.style.SUCCESS(
      f"Notes: {created} created, {updated} updated, {len(rows)} total; "
      f"{people} people and {tags} tag links, {rewritten} old-site links rewritten."
    ))
