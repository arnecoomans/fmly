from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError

from core.models import Tag
from core.tags import LOOSE_END_SLUG

# Seeing is not a permission: visibility decides that (every signed-in
# account sees what's shared with members). The groups decide what one may do.
VISITORS = 'Visitors'
EDITORS = 'Editors'
VISITOR_PERMISSIONS = ['core.add_comment']
# Adding and changing the archive - no delete: deleting goes through an
# object's status (StatusActionsForm), which is a change.
EDITED = {
  'content': ['content', 'photocontent', 'documentcontent', 'bookcontent', 'portrait', 'transcript'],
  'people': ['person', 'personrelation'],
  'events': ['event'],
  'places': ['place'],
  'notes': ['note'],
  'core': ['tag', 'comment'],
}
EDITOR_PERMISSIONS = [f'{app}.{action}_{model}' for app, models in EDITED.items() for model in models for action in ('add', 'change', 'view')]


def permissions(names):
  found = []
  for name in names:
    app_label, codename = name.split('.')
    try:
      found.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    except Permission.DoesNotExist:
      raise CommandError(f"Permission {name} doesn't exist - run migrate first.")
  return found


class Command(BaseCommand):
  help = (
    "Set up what a fresh database needs: the \"Loose end\" "
    "tag (core.tags.LOOSE_END_SLUG), and the groups Visitors (may comment) "
    "and Editors (may add and change the archive). Every active account "
    "without a group joins Visitors; with --all-editors every active account "
    "joins both (the family accounts moved from FMLY 2). Idempotent: a group's permissions are "
    "set to the ones listed here, so re-running undoes changes made in the admin."
  )

  def add_arguments(self, parser):
    parser.add_argument('--all-editors', action='store_true', help="Every active account joins Visitors and Editors.")

  def handle(self, *args, **options):
    User = get_user_model()
    owner = User.objects.filter(is_superuser=True).order_by('pk').first()
    if owner is None:
      raise CommandError("No superuser yet - import the users (or createsuperuser) first: the tag needs an owner.")

    tag, created = Tag.objects.get_or_create(
      slug=LOOSE_END_SLUG, parent=None,
      defaults={
        'name': 'Loose end', 'user': owner, 'status': 'p', 'visibility': 'c',
        'description': 'Marks something to come back to - listed on the dashboard under loose ends.',
      },
    )
    self.stdout.write(f"Tag \"{tag.name}\": {'created' if created else 'exists'}.")

    for name, names in ((VISITORS, VISITOR_PERMISSIONS), (EDITORS, EDITOR_PERMISSIONS)):
      group, created = Group.objects.get_or_create(name=name)
      group.permissions.set(permissions(names))
      self.stdout.write(f"Group {name}: {'created' if created else 'updated'}, {len(names)} permissions.")

    visitors = Group.objects.get(name=VISITORS)
    if options['all_editors']:
      editors = Group.objects.get(name=EDITORS)
      users = list(User.objects.filter(is_active=True))
      for user in users:
        user.groups.add(visitors, editors)
      self.stdout.write(self.style.SUCCESS(f"{len(users)} active account(s) in {VISITORS} and {EDITORS}."))
      return
    joining = list(User.objects.filter(is_active=True, groups__isnull=True))
    for user in joining:
      user.groups.add(visitors)
    self.stdout.write(self.style.SUCCESS(f"{len(joining)} account(s) without a group joined {VISITORS}."))
