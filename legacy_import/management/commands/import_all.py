from django.core.management import call_command
from django.core.management.base import BaseCommand

# In dependency order: users own everything; people link to users; events
# link people and places; people again, now for their dateless deaths
# (only where the events hold no death - import_persons --no-dateless-deaths);
# content links people, tags and events (and completes the event links,
# legacy_import/links.py); notes link to the new pages of people and content.
STEPS = [
  ('import_users', {}),
  ('import_places', {}),
  ('import_persons', {'no_dateless_deaths': True}),
  ('import_person_relations', {}),
  ('import_content_tags', {}),
  ('import_events', {}),
  ('import_persons', {}),
  ('import_content', {}),
  ('import_notes', {}),
]
# After the import: what a fresh database needs besides it.
AFTER = [
  ('content_checksums', {}),   # an upload of a file already in the archive is recognised
  ('prepare_release', {'all_editors': True}),   # the Loose end tag, the groups; the family accounts Visitors and Editors
  ('create_default_pages', {}),   # the cookie statement, in English and Dutch
]


class Command(BaseCommand):
  help = (
    "The whole legacy import from import/ (fixtures and documents, default "
    "paths), in dependency order - " + ", ".join(name for name, _o in STEPS) + " - then "
    + " and ".join(name for name, _o in AFTER) + ". Each step is idempotent, so a re-run updates "
    "rather than duplicates. Stops at the first step that fails. --skip-after: "
    "only the import."
  )

  def add_arguments(self, parser):
    parser.add_argument('--skip-after', action='store_true', help="Don't run " + " / ".join(name for name, _o in AFTER) + " afterwards.")

  def handle(self, *args, **options):
    steps = STEPS + ([] if options['skip_after'] else AFTER)
    for number, (step, step_options) in enumerate(steps, 1):
      flags = ' '.join(f"--{name.replace('_', '-')}" for name in step_options)
      self.stdout.write(self.style.MIGRATE_HEADING(f"[{number}/{len(steps)}] {step} {flags}".rstrip()))
      call_command(step, stdout=self.stdout, stderr=self.stderr, **step_options)
    self.stdout.write(self.style.SUCCESS(f"Done: {len(steps)} steps."))
