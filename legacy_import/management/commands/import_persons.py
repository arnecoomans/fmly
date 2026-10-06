import json
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from events.models import Event
from people.models import Person

User = get_user_model()


class Command(BaseCommand):
  help = (
    "Import people from import/fixtures/archive_person.json (a raw "
    "dumpdata export from the old environment). Field names on the old "
    "model don't match their new equivalents 1:1 - most importantly, old "
    "first_names ('all official first names') maps to new given_name, and "
    "old given_name ('the called name, if different') maps to new "
    "called_name - a same-name copy would silently swap them. "
    "portrait_x/y/w/h has no home on the new Person (belongs to a future "
    "Content import) - deliberately left alone in the fixture, not "
    "migrated here, not lost. moment_of_death_unconfirmed=True gets a "
    "dateless DEATH Event created for that person (kind=DEATH, no "
    "year/month/day) - 'confirmed dead, no details' per Event's own "
    "design (the same as \"Died, details unknown\" on a person's page, "
    "people/forms.py PersonDeathForm), skipped for the ~4 of "
    "16 flagged people who already have a real dated death event from the "
    "regular events import (the old flag apparently meant something "
    "narrower for those, not 'no death event exists')."
  )

  def add_arguments(self, parser):
    parser.add_argument(
      '--path', default=None,
      help="Path to the fixture (default: import/fixtures/archive_person.json)",
    )
    # The dateless deaths need the legacy events in place: a person with a
    # dated death among them gets none, and an event created before
    # import_events would take a legacy event's pk (and be overwritten by
    # it). import_all runs this twice: without them before import_events,
    # with them after.
    parser.add_argument(
      '--no-dateless-deaths', action='store_true',
      help="Don't create the dateless death events (run again after import_events for them).",
    )

  def handle(self, *args, **options):
    path = Path(options['path']) if options['path'] else Path(settings.BASE_DIR) / 'import' / 'fixtures' / 'archive_person.json'
    rows = json.loads(path.read_text())

    created, updated, emails_set, dateless_deaths_created = 0, 0, 0, 0

    for row in rows:
      f = row['fields']

      obj, was_created = Person.objects.update_or_create(
        pk=row['pk'],
        defaults={
          'token': f.get('token', ''),
          'status': f.get('status', 'p'),
          'given_name': f.get('first_names', ''),   # old "all first names" -> new given_name
          'called_name': f.get('given_name', ''),   # old "called name" -> new called_name
          'last_name': f.get('last_name', ''),
          'married_name': f.get('married_name', ''),
          'nickname': f.get('nickname', ''),
          'slug': f.get('slug', ''),
          'gender': f.get('gender', Person.Gender.UNKNOWN),
          'biography': f.get('bio', ''),
          'private': f.get('private', False),
          'related_user_id': f.get('related_user'),
          'user_id': f['user'],
          'visibility': Person.Visibility.COMMUNITY,  # old model had no visibility concept
        },
      )
      if was_created:
        created += 1
      else:
        updated += 1

      # auto_now_add/auto_now overwrite whatever's assigned at save() time,
      # unconditionally - only a separate queryset .update() (raw SQL, no
      # pre_save()) actually makes the original dates stick.
      Person.objects.filter(pk=obj.pk).update(
        date_created=parse_datetime(f['date_created']),
        date_modified=parse_datetime(f['date_modified']),
      )

      # 3 records in the old data have a per-person email with no home on
      # the new Person - carry it onto the linked User, but only if that
      # User doesn't already have one set (don't clobber a real login email).
      if f.get('email') and f.get('related_user'):
        emails_set += User.objects.filter(pk=f['related_user'], email='').update(email=f['email'])

      # Skip if a death event (dated or not) already exists - don't
      # duplicate, and don't second-guess a real dated death record just
      # because the old flag was also set on it.
      if not options['no_dateless_deaths'] and f.get('moment_of_death_unconfirmed') and not Event.objects.filter(
        people=obj, kind=Event.Kind.DEATH,
      ).exists():
        death_event = Event.objects.create(kind=Event.Kind.DEATH, user_id=f.get('user') or 1)
        death_event.people.set([obj])
        dateless_deaths_created += 1

    self.stdout.write(self.style.SUCCESS(
      f"People: {created} created, {updated} updated, {len(rows)} total "
      f"({emails_set} old per-person email(s) actually carried over to a "
      f"blank User.email, {dateless_deaths_created} dateless death "
      f"event(s) created for moment_of_death_unconfirmed people)."
    ))
