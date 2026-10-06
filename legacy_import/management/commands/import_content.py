import filecmp
import json
import os
import re
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from content.crop import image_geometry
from content.files import content_upload_to
from content.models import Content, Portrait
from django.contrib.contenttypes.models import ContentType

from core.models import Comment, Tag
from people.models import Person
from legacy_import.links import link_event_images, rewrite_old_links
from legacy_import.pk_offsets import ATTACHMENT_CONTENT_PK_OFFSET, BOOK_CONTENT_PK_OFFSET
from legacy_import.tag_layout import COLORIZATION_MARKER_SLUG, IMPORTED_TAG_ACCESS, ensure_access, tag_layout
from legacy_import.sequences import reset_sequences

# Every legacy document is Dutch unless changed by hand afterwards.
LEGACY_DOCUMENT_LANGUAGE = 'nl'

# archive_category pk -> (kind, photo_kind / document_kind). See
# docs/FMLY-3.0-PLAN.md, Content, "Import".
CATEGORY_KIND = {
  1: ('photo', 'other'),              # Photo
  7: ('photo', 'portrait'),           # Portrait
  2: ('document', None),              # Document - classified by title below
  3: ('document', 'newspaper'),       # News-article
  4: ('document', 'advertisement'),   # Advertisement
  5: ('object', None),                # Artwork
  8: ('object', None),                # Physical
  6: ('unknown', None),               # Uncategorized
}

# Title keywords -> document_kind, for Document-category items and PDFs.
# First match wins; anything else is 'other'.
DOCUMENT_KIND_RULES = [
  (r'paspoort|toeristenkaart', 'identity'),
  (r'interneringskaart|pow card|oorlogsgraf|stempels en symbolen', 'war_record'),
  (r'stamkaart|stamboek|pensioenkaart|militieregister', 'service_record'),
  (r'akte|overlijden|geboorte|huwelijk|bevolkingsregister|inschrijving|registratie', 'civil_record'),
  (r'almanak|naamlijst|adres ?boek|adreslijst|telepon|patriciaat|levensbericht', 'publication_excerpt'),
  (r'stamboom|archief|documents for', 'research'),
]

# archive_attachment files that aren't documents, by filename prefix.
ATTACHMENT_KIND_OVERRIDES = {
  'leerboek_der_verloskunde': 'book',  # a full book, by H.A. Bake
  'familiewapen': 'object',            # the Bake coat of arms
}


# A trailing file extension in a legacy title/description - some were set
# to the uploaded filename ("... goed beu.pdf", "... actief.jp2.jpg").
_TRAILING_EXTENSION = re.compile(r'\.(pdf|jpe?g|jp2|png|gif|tiff?|heic|mp3|mp4|mov|docx?|epub)\s*$', re.IGNORECASE)


def clean_name(name):
  """A legacy name without trailing file extension(s) - stripped
  repeatedly, for a double one like .jp2.jpg. Otherwise unchanged."""
  name = (name or '').strip()
  while _TRAILING_EXTENSION.search(name):
    name = _TRAILING_EXTENSION.sub('', name).strip()
  return name


def document_kind_for(title, description=''):
  """By title first; only when that says nothing, by description - many
  almanac excerpts have a topical title ('Zoutregie') and name their
  source in the description ('Uit: Regeerings-almanak ...')."""
  for text in (title, description):
    text = (text or '').lower()
    for pattern, kind in DOCUMENT_KIND_RULES:
      if re.search(pattern, text):
        return kind
  return 'other'


class Command(BaseCommand):
  help = (
    "Import legacy content - archive_image (367), archive_attachment (20) and "
    "archive_book (44) - into content.Content, with files from "
    "import/documents/. Mapping per docs/FMLY-3.0-PLAN.md, Content, "
    "'Import': category -> kind + photo/document kind, portrait_of -> "
    "Portrait (no crop), groups / image attachments / collections -> tags. "
    "Records whose file isn't in import/documents/ are created without it "
    "(original_filename records what to look for). Idempotent: rerunning "
    "updates records and only copies files that aren't stored yet. Image "
    "pks are kept; attachment and book pks are offset (legacy_import/"
    "pk_offsets.py). Requires import_users, import_persons and "
    "import_content_tags to have run first."
  )

  def add_arguments(self, parser):
    parser.add_argument('--fixtures', default=None, help="Default: import/fixtures/")
    parser.add_argument('--documents', default=None, help="Default: import/documents/")
    parser.add_argument(
      '--files-only', action='store_true',
      help="Only attach files now found in import/documents/ to existing records that have none - "
           "nothing else is created or changed (edits made on the site stay). Sets their checksums.",
    )

  def handle(self, *args, **options):
    base = Path(settings.BASE_DIR) / 'import'
    self.fixtures = Path(options['fixtures']) if options['fixtures'] else base / 'fixtures'
    self.documents = Path(options['documents']) if options['documents'] else base / 'documents'
    self.stats = {'comments': 0, 'comments_skipped': 0, 'links_rewritten': 0, 'created': 0, 'updated': 0, 'files': 0, 'reused': 0, 'moved': 0, 'missing': 0, 'portraits': 0, 'crops': 0, 'tags': 0}

    images = self.load('archive_image')
    attachments = self.load('archive_attachment')
    books = self.load('archive_book')

    if options['files_only']:
      self.attach_missing_files(images, attachments, books)
      return

    for row in images:
      self.import_image(row)
    for row in attachments:
      self.import_attachment(row)
    for row in books:
      self.import_book(row)

    self.import_portrait_crops()
    self.import_groups(images)
    self.import_attachment_links(images, books)
    self.import_collections()
    self.import_comments()
    # Event <-> content links (archive_event.images). Also done by
    # import_events - whichever of the two runs last completes the set.
    self.stats['event_links'], self.stats['event_links_waiting'] = link_event_images(self.fixtures)

    reset_sequences()   # PostgreSQL: new rows get ids after the imported ones (legacy_import/sequences.py)
    self.stdout.write(self.style.SUCCESS(
      "Content: {created} created, {updated} updated; {files} files copied, {reused} reused, "
      "{moved} moved, {missing} records without a file; {portraits} portraits, {crops} crops set; "
      "{tags} tag links; {event_links} event links, {event_links_waiting} waiting for events "
      "(run import_events); {comments} comments ({comments_skipped} skipped, "
      "{links_rewritten} old-site links rewritten).".format(**self.stats)
    ))

  # --- helpers ---------------------------------------------------------------

  def load(self, name):
    return json.loads((self.fixtures / f'{name}.json').read_text())

  def upsert(self, pk, fields, legacy_file, dates):
    """Create or update Content pk with fields; attach legacy_file from
    import/documents/ if it's there and nothing is stored yet."""
    content = Content.objects.filter(pk=pk).first()
    created = content is None
    if created:
      content = Content(pk=pk)
    stored_before = content.file.name if content.file else ''
    for key, value in fields.items():
      setattr(content, key, value)
    basename = os.path.basename(legacy_file or '')
    content.original_filename = basename
    # The legacy date_created decides the year folder (content/files.py),
    # so it's set before anything is saved or filed: an existing record's
    # save() then moves its file into the right year, and a new record's
    # file (attached below) is stored there right away. On insert,
    # auto_now_add overwrites it - hence the update.
    legacy_created = parse_datetime(dates['date_created'])
    content.date_created = legacy_created
    content.save()
    if created:
      Content.objects.filter(pk=content.pk).update(date_created=legacy_created)
      content.date_created = legacy_created
    if basename and not content.file:
      self.attach_file(content, basename)
    # A file stored by an earlier run in another year folder was moved by
    # save() -> sync_filename() above, once date_created was set.
    if stored_before and content.file.name != stored_before:
      self.stats['moved'] += 1
    Content.objects.filter(pk=content.pk).update(date_modified=parse_datetime(dates['date_modified']))
    self.stats['created' if created else 'updated'] += 1
    return content

  def attach_file(self, content, basename):
    """Store the legacy file for a record without one, if it's in
    import/documents/ - reusing an identical stored copy. Returns 'files',
    'reused' or 'missing' (also counted in self.stats)."""
    path = self.find_document(basename)
    if path is None:
      outcome = 'missing'
    elif existing := self.existing_copy(content, path, basename):
      content.file.name = existing
      content.save()
      outcome = 'reused'
    else:
      with path.open('rb') as handle:
        content.file.save(basename, File(handle), save=True)
      outcome = 'files'
    self.stats[outcome] += 1
    return outcome

  def attach_missing_files(self, images, attachments, books):
    """--files-only: for each legacy record that exists here without a
    file, attach it if import/documents/ has it now - and its checksum
    (content/uploads.py). Nothing else is touched."""
    from content.uploads import checksum_of
    sources = (
      [(row['pk'], row['fields']['source']) for row in images]
      + [(row['pk'] + ATTACHMENT_CONTENT_PK_OFFSET, row['fields']['file']) for row in attachments]
      + [(row['pk'] + BOOK_CONTENT_PK_OFFSET, row['fields']['cover']) for row in books]
    )
    for pk, legacy_file in sources:
      basename = os.path.basename(legacy_file or '')
      content = Content.objects.filter(pk=pk).first()
      if not basename or content is None or content.file:
        continue
      if content.original_filename != basename:
        # Its file name decides the stored name (content/files.py), as on import.
        Content.objects.filter(pk=pk).update(original_filename=basename)
        content.original_filename = basename
      modified = content.date_modified   # attaching a file isn't an edit
      if self.attach_file(content, basename) != 'missing':
        with content.file.open('rb') as handle:
          Content.objects.filter(pk=pk).update(checksum=checksum_of(handle), date_modified=modified)
    self.stdout.write(self.style.SUCCESS(
      "Files only: {files} files copied, {reused} reused, {missing} still missing.".format(**self.stats)
    ))

  def find_document(self, basename):
    """The file in import/documents/ for a legacy name - exactly, or with
    underscores as spaces: the old site stored 'De_Japanse_Burgerkampen.JPG'
    for a file supplied later as 'De Japanse Burgerkampen.JPG'. None if
    neither exists."""
    for name in (basename, basename.replace('_', ' ')):
      path = self.documents / name
      if path.exists():
        return path
    return None

  def existing_copy(self, content, source, basename):
    """An identical file already stored where this record's file would go -
    e.g. after a development reload that reset the database but kept
    private/. Returns its storage name, or None to copy the file.

    Candidates: the target name, or it with the _abc1234 suffix Django adds
    on a name collision. Only a file no OTHER record uses: two records
    (a book cover that's also an image record) must never share one file,
    or renaming one would break the other."""
    storage = content.file.storage
    target = content_upload_to(content, basename)
    directory, name = os.path.split(target)
    stem, ext = os.path.splitext(name)
    try:
      _, files = storage.listdir(directory)
    except FileNotFoundError:
      return None
    pattern = re.compile(re.escape(stem) + r'(_[A-Za-z0-9]{7})?' + re.escape(ext))
    size = source.stat().st_size
    for filename in sorted(files):
      candidate = f"{directory}/{filename}"
      if not pattern.fullmatch(filename) or storage.size(candidate) != size:
        continue
      if Content.objects.filter(file=candidate).exclude(pk=content.pk).exists():
        continue
      if filecmp.cmp(storage.path(candidate), source, shallow=False):
        return candidate
    return None

  def set_detail_kind(self, content, sub_kind):
    """photo_kind / document_kind on the detail - and for documents the
    language: Dutch for the whole legacy archive."""
    detail = content.get_detail()
    if detail is None or sub_kind is None:
      return
    field = {'photo': 'photo_kind', 'document': 'document_kind'}.get(content.kind)
    if field:
      setattr(detail, field, sub_kind)
    if content.kind == 'document':
      detail.language = LEGACY_DOCUMENT_LANGUAGE
    detail.save()

  def tag(self, name, description='', user_id=1, collection=False, colorization=False):
    """A tag by legacy slug - reused if it exists (groups merge into tags,
    e.g. group 'Medan' into tag 'medan'). Root-level, or under
    "Collection" / "Colorization", renamed where decided - both from
    legacy_import/tag_layout.py, so a re-import keeps them. The slug stays
    the legacy one, so the tag is found again after a rename."""
    slug = slugify(name)
    name, parent = tag_layout(slug, name, collection=collection, colorization=colorization)
    tag = Tag.objects.filter(slug=slug, parent=parent).first()
    if tag is None:
      tag = Tag.objects.create(name=name, slug=slug, parent=parent, description=description or '', user_id=user_id, **IMPORTED_TAG_ACCESS)
    return ensure_access(tag)

  def add_tags(self, contents, tags):
    for content in contents:
      content.tags.add(*tags)
      self.stats['tags'] += len(tags)

  # --- sources ---------------------------------------------------------------

  def import_image(self, row):
    f = row['fields']
    kind, sub_kind = CATEGORY_KIND.get(f['category'], ('unknown', None))
    if kind == 'document' and sub_kind is None:
      sub_kind = document_kind_for(f['title'], f['description'])
    content = self.upsert(row['pk'], {
      'kind': kind,
      'name': clean_name(f['title']),
      'description': f['description'] or '',
      'source': f['document_source'] or '',
      'status': f['status'],
      'user_id': f['user'] or 1,
      'year': f['year'], 'month': f['month'], 'day': f['day'],
    }, f['source'], f)
    self.set_detail_kind(content, sub_kind)
    content.people.set(f['people'])
    content.tags.set(f['tag'])
    for person_id in f['portrait_of']:
      _, created = Portrait.objects.get_or_create(
        person_id=person_id, content=content, defaults={'is_primary': True},
      )
      self.stats['portraits'] += created

  def import_attachment(self, row):
    f = row['fields']
    basename = os.path.basename(f['file'])
    stem, ext = os.path.splitext(basename.lower())
    kind = next((k for prefix, k in ATTACHMENT_KIND_OVERRIDES.items() if stem.startswith(prefix)), None)
    if kind is None:
      kind = {'.pdf': 'document', '.mp3': 'recording', '.mp4': 'recording'}.get(ext, 'unknown')
    content = self.upsert(row['pk'] + ATTACHMENT_CONTENT_PK_OFFSET, {
      'kind': kind,
      'name': clean_name(f['description']),
      'status': f['status'],
      'user_id': f['user'] or 1,
    }, f['file'], f)
    if kind == 'document':
      self.set_detail_kind(content, document_kind_for(f['description']))

  def import_book(self, row):
    f = row['fields']
    content = self.upsert(row['pk'] + BOOK_CONTENT_PK_OFFSET, {
      'kind': 'book',
      'name': clean_name(f['title']),
      'description': f['description'] or '',
      'status': f['status'],
      'user_id': f['user'] or 1,
      'year': f['year'],   # the year published: a book's date (no year of its own)
    }, f['cover'], f)
    detail = content.get_detail()
    detail.author = f['author'] or ''
    detail.publisher = f['publisher'] or ''
    detail.isbn = f['isbn'] or ''
    detail.save()

  def import_portrait_crops(self):
    """archive_person.portrait_x/y/w/h -> the person's primary Portrait crop.

    Legacy crops are pixels; Portrait stores fractions of the image as
    displayed. Converted against the ACTUAL file's size (header only), not
    the legacy width/height: three legacy images record 300 x 263 (a
    thumbnail size) while the file and the crop are ~2930 x 2570. None of
    the portrait files carries an EXIF rotation, so stored = displayed.
    Only fills an empty crop - a crop adjusted since isn't overwritten by
    a rerun."""
    for row in self.load('archive_person'):
      f = row['fields']
      if not f.get('portrait_w') or not f.get('portrait_h'):
        continue
      link = Portrait.objects.filter(person_id=row['pk'], is_primary=True, crop_w__isnull=True).select_related('content').first()
      if link is None or not link.content.file:
        continue
      try:
        width, height, _orientation = image_geometry(link.content.file.path)
      except FileNotFoundError:
        continue
      clamp = lambda value: min(max(value, 0.0), 1.0)
      link.crop_x = clamp(f['portrait_x'] / width)
      link.crop_y = clamp(f['portrait_y'] / height)
      link.crop_w = clamp(f['portrait_w'] / width)
      link.crop_h = clamp(f['portrait_h'] / height)
      link.crop_w = min(link.crop_w, 1 - link.crop_x)
      link.crop_h = min(link.crop_h, 1 - link.crop_y)
      link.full_clean()
      link.save()
      self.stats['crops'] += 1

  def rewrite_old_links(self, text):
    """Old-site links -> the new pages (legacy_import/links.py)."""
    text, rewritten = rewrite_old_links(text)
    self.stats['links_rewritten'] += rewritten
    return text

  def import_comments(self):
    """archive_comment (39, all on images) -> core.Comment on the image's
    Content (pks kept). Legacy pk, token, author, status (p / x) and dates
    kept; visibility community; old-site links rewritten. An empty comment
    is skipped (content is required). Idempotent."""
    content_type = ContentType.objects.get_for_model(Content)
    for row in self.load('archive_comment'):
      f = row['fields']
      text = (f.get('content') or '').strip()
      if not text or not Content.objects.filter(pk=f['image']).exists():
        self.stats['comments_skipped'] += 1
        continue
      comment, _ = Comment.objects.update_or_create(pk=row['pk'], defaults={
        'token': f['token'], 'target_content_type': content_type, 'target_id': f['image'],
        'user_id': f['user'] or 1, 'content': self.rewrite_old_links(text),
        'status': f['status'], 'visibility': Comment.Visibility.COMMUNITY,
      })
      Comment.objects.filter(pk=comment.pk).update(
        date_created=parse_datetime(f['date_created']), date_modified=parse_datetime(f['date_modified']),
      )
      self.stats['comments'] += 1

  def import_groups(self, images):
    """archive_group -> a tag per group (merged into an existing tag with
    the same slug), on every image in it, plus the group's own tags. A
    colorization group (marked with the legacy tag "ingekleurd": an
    original and its colorized version) gets its tag under
    "Colorization" - so groups 'Boot' and 'Medan' no longer merge into
    the topical tags 'boot' and 'medan'."""
    groups = {row['pk']: row['fields'] for row in self.load('archive_group')}
    for group_pk, g in groups.items():
      members = Content.objects.filter(pk__in=[r['pk'] for r in images if group_pk in r['fields']['in_group']])
      own_tags = list(Tag.objects.filter(pk__in=g['tag']))
      colorization = any(t.slug == COLORIZATION_MARKER_SLUG for t in own_tags)
      tags = [self.tag(g['title'], g['description'], g['user'] or 1, colorization=colorization), *own_tags]
      self.add_tags(members, tags)

  def import_attachment_links(self, images, books):
    """An image or book with attachments -> a tag named after it, on the
    item and each of its attachments (decided: grouped via tags)."""
    for rows, offset in ((images, 0), (books, BOOK_CONTENT_PK_OFFSET)):
      for row in rows:
        attachment_ids = row['fields']['attachments']
        if not attachment_ids:
          continue
        tag = self.tag(row['fields']['title'], user_id=row['fields']['user'] or 1)
        linked = Content.objects.filter(pk__in=[
          row['pk'] + offset, *[a + ATTACHMENT_CONTENT_PK_OFFSET for a in attachment_ids],
        ])
        self.add_tags(linked, [tag])

  def import_collections(self):
    """archive_collection -> a tag per collection, under "Collection", on
    its books; the collection item's read flag is dropped."""
    collections = {row['pk']: row['fields'] for row in self.load('archive_collection')}
    for item in self.load('archive_collectionitem'):
      c = collections[item['fields']['collection']]
      book = Content.objects.filter(pk=item['fields']['book'] + BOOK_CONTENT_PK_OFFSET).first()
      if book:
        self.add_tags([book], [self.tag(c['name'], c['description'] or '', c['user'] or 1, collection=True)])
