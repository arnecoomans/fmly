import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

User = get_user_model()


class Command(BaseCommand):
  help = (
    "Import users from import/fixtures/auth_user.json (a raw dumpdata "
    "export from the old environment). Deliberately does NOT use loaddata: "
    "the old fixture's groups/user_permissions reference auth.Group/"
    "Permission rows from the old system that don't exist here, and this "
    "project has no equivalent group/permission setup to map them onto - "
    "they're dropped, not deferred. Everything else (username, password "
    "hash, name, email, is_staff/is_superuser/is_active, date_joined, "
    "last_login) is preserved as-is, including the pk, since every other "
    "imported fixture references users by these exact ids."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      '--path', default=None,
      help="Path to the fixture (default: import/fixtures/auth_user.json)",
    )

  def handle(self, *args, **options):
    path = Path(options['path']) if options['path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'auth_user.json'
    rows = json.loads(path.read_text())

    created, updated, skipped_groups = 0, 0, 0

    for row in rows:
      f = row['fields']
      if f.get('groups') or f.get('user_permissions'):
        skipped_groups += 1

      obj, was_created = User.objects.update_or_create(
        pk=row['pk'],
        defaults={
          'username': f['username'],
          'password': f['password'],  # already-hashed - preserved verbatim, not re-hashed
          'first_name': f.get('first_name', ''),
          'last_name': f.get('last_name', ''),
          'email': f.get('email', ''),
          'is_staff': f.get('is_staff', False),
          'is_superuser': f.get('is_superuser', False),
          'is_active': f.get('is_active', True),
          'date_joined': parse_datetime(f['date_joined']),
          'last_login': parse_datetime(f['last_login']) if f.get('last_login') else None,
        },
      )
      if was_created:
        created += 1
      else:
        updated += 1

    self.stdout.write(self.style.SUCCESS(
      f"Users: {created} created, {updated} updated, {len(rows)} total "
      f"({skipped_groups} had groups/permissions dropped - no equivalent in this project)."
    ))
