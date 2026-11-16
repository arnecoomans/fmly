import os
import pwd

from django.conf import settings
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError

from content.models import Content
from content.uploads import create_upload

# What a browser's <audio> / <video> plays - anything else uploads and
# downloads fine, but the player on the item's page stays blank.
PLAYABLE = {'.mp4', '.m4v', '.webm', '.ogv', '.mp3', '.m4a', '.aac', '.ogg', '.oga', '.opus', '.wav', '.flac'}


class Command(BaseCommand):
  help = (
    "Add files that are too big for the web uploader (a long video, a "
    "podcast) - copied to the server first. Each file goes the uploader's "
    "way (content/uploads.py create_upload): a draft in the user's inbox, "
    "the kind guessed from the file, read in chunks; a file that's in the "
    "archive already is reported and skipped. A folder adds the files in it "
    "(not its subfolders). --user: whose inbox - the first superuser when "
    "left out. Run as the owner of MEDIA_ROOT (on the server: sudo -u fmly), "
    "so the stored files belong to the site."
  )

  def add_arguments(self, parser):
    parser.add_argument('paths', nargs='+', help="Files, or folders of files.")
    parser.add_argument('--user', help="Username whose inbox the drafts land in (default: the first superuser).")
    parser.add_argument('--delete-source', action='store_true', help="Remove each file here once it's stored (never a duplicate's).")

  def handle(self, *args, paths, user=None, delete_source=False, **options):
    self._check_account()
    owner = self._owner(user)
    files = self._files(paths)
    added = duplicates = failed = 0
    for path in files:
      name = os.path.basename(path)
      try:
        with open(path, 'rb') as handle:
          content, duplicate = create_upload(File(handle, name=name), owner)
      except OSError as error:
        failed += 1
        self.stderr.write(self.style.ERROR(f"{name}: not added - {error}"))
        continue
      if duplicate is not None:
        duplicates += 1
        status = f", {duplicate.get_status_display()}" if duplicate.status != Content.Status.PUBLISHED else ''
        self.stdout.write(self.style.WARNING(f"{name}: in the archive already - {duplicate} ({duplicate.get_absolute_url()}{status}); skipped"))
        continue
      LogEntry.objects.log_actions(owner.pk, [content], ADDITION, change_message="Uploaded (manage.py content_add)", single_object=True)
      added += 1
      self.stdout.write(f"{name}: added as a {content.get_kind_display()} - {content.get_absolute_url()}")
      if content.media_type in ('audio', 'video') and os.path.splitext(name)[1].lower() not in PLAYABLE:
        self.stdout.write(self.style.WARNING(
          f"  {name}: browsers can't play this format - the player stays blank. "
          "Converted first it plays (and is often much smaller): ffmpeg -i in.avi -c:v libx264 -c:a aac out.mp4"
        ))
      if delete_source:
        os.remove(path)
    self.stdout.write(self.style.SUCCESS(
      f"{added} added to {owner.get_username()}'s inbox, {duplicates} in the archive already, {failed} failed."
    ))
    if failed:
      raise CommandError(f"{failed} file(s) not added.")

  def _check_account(self):
    """Stop unless this runs as the owner of MEDIA_ROOT - the web process's
    account (the site user on the server; you, locally). Run as the admin or
    root, the stored files would belong to them, not the site."""
    stat = os.stat(settings.MEDIA_ROOT)
    if os.geteuid() != stat.st_uid:
      try:
        account = pwd.getpwuid(stat.st_uid).pw_name
      except KeyError:
        account = str(stat.st_uid)
      raise CommandError(
        f"Run this as {account}, who owns {settings.MEDIA_ROOT} - so the stored files belong to the site: "
        f"sudo -u {account} .venv/bin/python manage.py content_add …"
      )

  def _owner(self, username):
    """The user whose inbox it is - named, or the first superuser. Must be
    active and allowed to upload, as on the site."""
    User = get_user_model()
    if username:
      owner = User.objects.filter(**{User.USERNAME_FIELD: username}).first()
      if owner is None:
        raise CommandError(f"No user '{username}'.")
    else:
      owner = User.objects.filter(is_superuser=True, is_active=True).order_by('pk').first()
      if owner is None:
        raise CommandError("No active superuser - name a user with --user.")
      self.stdout.write(f"No --user: into the inbox of {owner.get_username()} (the first superuser).")
    if not (owner.is_active and owner.has_perm('content.add_content')):
      raise CommandError(f"{owner.get_username()} may not upload (inactive, or no content.add_content).")
    return owner

  def _files(self, paths):
    """Each path, a folder's files (not hidden ones, not subfolders) in
    name order. A path that's neither: stop before anything is added."""
    files = []
    for path in paths:
      if os.path.isdir(path):
        files += sorted(
          os.path.join(path, entry) for entry in os.listdir(path)
          if not entry.startswith('.') and os.path.isfile(os.path.join(path, entry))
        )
      elif os.path.isfile(path):
        files.append(path)
      else:
        raise CommandError(f"Not a file or folder: {path}")
    if not files:
      raise CommandError("No files to add.")
    return files
