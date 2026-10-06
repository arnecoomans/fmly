from django.core.management.base import BaseCommand
from django.db.models import Count

from content.models import Content
from content.uploads import checksum_of


class Command(BaseCommand):
  help = (
    "Fill in the checksum (SHA-256) of every content file that hasn't one - "
    "so an upload of a file that's in the archive already is recognised "
    "(content/uploads.py). Reads each file once, in chunks. Idempotent: run "
    "it after a deploy that adds the field, or after importing files. "
    "--all recomputes every checksum. Also measures images without a "
    "stored width and height (Content.measure; with --all every image)."
  )

  def add_arguments(self, parser):
    parser.add_argument('--all', action='store_true', help="Recompute every checksum, not only the missing ones.")

  def handle(self, *args, **options):
    items = Content.objects.exclude(file='')
    if not options['all']:
      items = items.filter(checksum='')
    done = missing = 0
    for content in items.iterator():
      try:
        with content.file.open('rb') as fileobj:
          checksum = checksum_of(fileobj)
      except FileNotFoundError:
        missing += 1
        continue
      Content.objects.filter(pk=content.pk).update(checksum=checksum)
      done += 1
    # Dimensions: images not measured yet (Content.measure - header only).
    measured = 0
    images = Content.objects.exclude(file='')
    if not options['all']:
      images = images.filter(width__isnull=True)
    for content in images.iterator():
      if content.media_type != 'image':
        continue
      content.measure()
      measured += content.width is not None
    duplicates = (
      Content.objects.exclude(checksum='').values('checksum').order_by().annotate(n=Count('pk')).filter(n__gt=1).count()
    )
    self.stdout.write(self.style.SUCCESS(
      f"Checksums: {done} computed, {missing} file(s) missing; {duplicates} file(s) stored more than once; "
      f"{measured} image(s) measured."
    ))
