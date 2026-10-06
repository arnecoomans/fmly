import mimetypes
import os

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext, gettext_lazy as _

from cmnsd.models.mixins import (
  TimestampMixin, TokenMixin, StatusMixin, OwnershipMixin,
  VisibilityMixin, PartialDateMixin, SlugMixin, EditableRelationsMixin,
)
from cmnsd.api.registry import api_action, api_model
from cmnsd.models.access import filter_accessible
from core.models import CommentableMixin

from ..files import content_upload_to, is_meaningless_filename, rename_content_file, split_filename


_fraction = [MinValueValidator(0.0), MaxValueValidator(1.0)]


class ContentQuerySet(models.QuerySet):
  def visible_to(self, request):
    """What this viewer may see: status, then visibility - the same
    cmnsd rule as VisibilityViewMixin.get_accessible_queryset(), for code
    that isn't a class-based view (the file and thumbnail views)."""
    return filter_accessible(self, request)

  def viewable_by(self, request):
    """What this viewer may open by its address: visible_to - and, for
    staff, deleted items too (their visibility still applies), marked
    deleted on their page: a duplicate is checked before it's purged
    (dashboard housekeeping). Only for an item's own page, its file and its
    thumbnails - lists, search, pickers and counts keep visible_to, so a
    deleted item is hardly ever linked."""
    visible = self.visible_to(request)
    user = getattr(request, 'user', None)
    if not (user and user.is_authenticated and user.is_staff):
      return visible
    from cmnsd.models.mixins import StatusMixin
    deleted = self.model.filter_visibility(self.filter(status=StatusMixin.Status.DELETED), request)
    return self.filter(models.Q(pk__in=visible.values('pk')) | models.Q(pk__in=deleted.values('pk')))

  def in_order(self, sort):
    """'date': chronologically by the item's own date, undated last;
    anything else ('added'): most recently added first. The two orders of
    the content grid's sort switch (content/_content_grid.html)."""
    if sort == 'date':
      return self.order_by(
        models.F('year').asc(nulls_last=True), models.F('month').asc(nulls_last=True),
        models.F('day').asc(nulls_last=True), 'name',
      )
    return self.order_by('-date_created', 'name')

  def for_list(self):
    """Hook for cmnsd.api.filtering.build_list() (the content list page and
    its live search): only wholes, detail rows included for the cards'
    kind labels. Ordered later, per viewer (content_tags.in_list_order)."""
    return self.listable().select_related('photo_detail', 'document_detail', 'book_detail')

  def listable(self):
    """What a content list shows: no parts of a book (parent set) - those
    appear under their book, in order."""
    return self.filter(parent__isnull=True)


@api_model(search_fields=['name', 'description'])
class Content(TimestampMixin, TokenMixin, SlugMixin, StatusMixin, OwnershipMixin, VisibilityMixin,
              PartialDateMixin, CommentableMixin, EditableRelationsMixin, models.Model):
  """Everything that is uploaded - one file per row. See
  docs/FMLY-3.0-PLAN.md, Content.

  kind is what the item IS; the file format is media_type, derived from
  the file, never chosen. Kind-specific fields live in a detail model
  (PhotoContent, DocumentContent, BookContent), created on save once the
  kind has one."""

  class Kind(models.TextChoices):
    UNKNOWN = "unknown", _("unknown")
    PHOTO = "photo", _("photo")
    DOCUMENT = "document", _("document")
    BOOK = "book", _("book")
    OBJECT = "object", _("object")
    RECORDING = "recording", _("recording")

  # SlugMixin: the slug names the file and is the readable part of the
  # page URL (content/<token>/<slug>/), so it follows the name - the token
  # keeps links stable. Not 'file'/'thumb'/'portrait'/'transcribe': those
  # are the segments of the file URLs and the transcribe page at the same
  # position.
  slug_follows_source = True
  reserved_slugs = ('file', 'thumb', 'portrait', 'transcribe')

  # Relations edited on the page (edit mode, cmnsd EditableRelationsMixin:
  # link / unlink). A tag can be created from the picker - published,
  # for members: one field, nothing to review (docs/EDIT-MODE-PLAN.md).
  # A place too (no status of its own): context - its parent region -
  # comes later by editing the place, or right away as "U.S.A.: New York"
  # (HierarchyMixin splits that into parent and child).
  # People aren't created here: a person needs more fields - the picker
  # links to the add page instead (content_detail.html, new_url).
  # Blocks of fields edited on the page (edit mode, cmnsd object_form):
  # name -> the form (dotted: content/forms.py imports this model). The
  # page shows content/blocks/<name>.html; see cmnsd/edit/block.html.
  api_edit_forms = {
    'name': 'content.forms.ContentNameForm',
    'description': 'content.forms.ContentDescriptionForm',
    'date': 'content.forms.ContentDateForm',
    'source': 'content.forms.ContentSourceForm',
    'thumbnail': 'content.forms.ContentThumbnailForm',   # in a dialog: the cropper
    'publication': 'content.forms.BookPublicationForm',
    'isbn': 'content.forms.BookIsbnForm',
    # choices - saved on click (cmnsd/edit/choices.html)
    'visibility': 'content.forms.ContentVisibilityForm',
    'kind': 'content.forms.ContentKindForm',
    'status': 'content.forms.ContentStatusForm',
    'photo_kind': 'content.forms.PhotoKindForm',
    'document_kind': 'content.forms.DocumentKindForm',
    'language': 'content.forms.DocumentLanguageForm',
  }

  # Child records edited on the page (cmnsd object_children): transcripts -
  # with their own permissions (content.add/change/delete_transcript).
  # Transcripts are written on the transcribe page (image beside text) -
  # 'page' sends the pencil and "+ add" there.
  api_editable_children = {
    'transcripts': {
      'form': 'content.forms.TranscriptForm',
      'add_label': _("add a transcript or translation"),
      'page': lambda content, transcript: (
        reverse('content:transcribe', args=[content.token]) + f"?transcript={transcript.pk if transcript else 'new'}"
      ),
    },
  }

  # Suggestions for recurring free text (cmnsd object_suggest): existing
  # values of that field among the items the viewer may see.
  api_suggest_fields = {'publisher': 'book_detail__publisher'}

  api_editable_relations = {
    'tags': {'create': {'status': 'p', 'visibility': 'c'}},
    'places': {'create': {}},
    'people': {},
    'events': {},   # like people: more fields - the picker links to the add page
    # A book's linked authors live on its detail (BookContent.authors) - only
    # for a book (an item that used to be one keeps its detail row).
    'authors': {'path': 'book_detail.authors', 'available': lambda content: content.kind == 'book'},
  }

  kind = models.CharField(max_length=20, choices=Kind.choices, default=Kind.UNKNOWN)
  # blank: legacy records are imported even when their file is missing.
  file = models.FileField(upload_to=content_upload_to, max_length=500, blank=True)
  original_filename = models.CharField(max_length=255, blank=True, help_text=_("The name the file arrived with"))
  # The file's fingerprint (SHA-256 of its bytes): an upload of a file that's
  # in the archive already is recognised (content/uploads.py). Filled for
  # existing files by `manage.py content_checksums`.
  checksum = models.CharField(max_length=64, blank=True, db_index=True, editable=False)
  name = models.CharField(max_length=255, blank=True)
  description = models.TextField(blank=True)
  source = models.CharField(max_length=1000, blank=True, help_text=_("Where this came from: a person, archive or URL"))

  # The item's own thumbnail (content.forms.ContentThumbnailForm): a 4:3
  # box - the card's shape - as fractions of the image turned by
  # thumb_rotation (clockwise) first, like a Portrait's crop. Used for the
  # 'card' and 'avatar' thumbnails (the square one centered in the box),
  # never for the large view. All empty = the center of the image.
  # An image's size in pixels as shown - EXIF rotation applied, so a phone
  # photo taken upright reads portrait (content/crop.py displayed_size).
  # Measured from the header when an image is saved new or changed, and
  # by manage.py content_checksums for what's there already.
  width = models.PositiveIntegerField(null=True, blank=True, editable=False)
  height = models.PositiveIntegerField(null=True, blank=True, editable=False)

  thumb_crop_x = models.FloatField(null=True, blank=True, validators=_fraction)
  thumb_crop_y = models.FloatField(null=True, blank=True, validators=_fraction)
  thumb_crop_w = models.FloatField(null=True, blank=True, validators=_fraction)
  thumb_crop_h = models.FloatField(null=True, blank=True, validators=_fraction)
  thumb_rotation = models.PositiveSmallIntegerField(
    default=0, choices=[(0, '0°'), (90, '90°'), (180, '180°'), (270, '270°')],
  )

  # Plain M2M until Mention exists (docs/FMLY-3.0-PLAN.md).
  people = models.ManyToManyField('people.Person', blank=True, related_name='content')
  tags = models.ManyToManyField('core.Tag', blank=True, related_name='content')
  places = models.ManyToManyField('places.Place', blank=True, related_name='content')
  # Events this item documents (a birth announcement for a birth). Plain M2M
  # until Mention exists - then Mention(role=proof), per the plan.
  events = models.ManyToManyField('events.Event', blank=True, related_name='content')
  portrait_of = models.ManyToManyField(
    'people.Person', through='content.Portrait', blank=True, related_name='portraits',
  )

  # Parts of a book (back cover, excerpts, ...), in order. Content lists
  # show only parent=None - see Content.objects.listable().
  parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='parts')
  position = models.PositiveIntegerField(default=0)

  objects = ContentQuerySet.as_manager()
  # Dismissed from a loose end ("fine as it is", dashboard.LooseEndDismissal):
  # the rows go with the item.
  loose_end_dismissals = GenericRelation('dashboard.LooseEndDismissal')

  class Meta:
    ordering = ['position', '-date_created']
    verbose_name = _("content")
    verbose_name_plural = _("content")

  def __str__(self):
    return self.name or self.original_filename or self.token

  @property
  def has_readable_slug(self):
    """A slug worth showing: not the token itself - an item without a name
    yet (a camera's IMG_1234) gets its token as slug, to name its file by."""
    return bool(self.slug) and self.slug != self.token.lower()

  def get_absolute_url(self):
    """content/<token>/<slug>/ - the token finds the item (stable), the
    slug is for people reading the URL; an outdated or missing slug
    redirects here (ContentDetailView). Without a readable slug - no name
    yet - just content/<token>/, not the token twice."""
    if not self.has_readable_slug:
      return reverse('content:detail_by_token', kwargs={'token': self.token})
    return reverse('content:detail', kwargs={'token': self.token, 'slug': self.slug})

  # Above this many pixels the original is too heavy to zoom into in a
  # browser (decoded, 260 MP is about a gigabyte); the 'xlarge' thumbnail
  # stands in, the original stays a click away ("open original").
  ZOOM_ORIGINAL_MAX_PIXELS = 40_000_000

  # Image formats browsers (other than Safari) can't show: zoomed into as a
  # JPEG rendering, like a giant scan.
  NOT_IN_BROWSERS = ('.heic', '.heif')

  def zoom_url(self):
    """What the lightbox loads when zoomed in past the 'large' view: the
    original file, or - for a giant scan, or a HEIC photo - the 'xlarge'
    thumbnail (JPEG)."""
    not_shown = os.path.splitext(self.file.name or '')[1].lower() in self.NOT_IN_BROWSERS
    if not_shown or (self.width and self.height and self.width * self.height > self.ZOOM_ORIGINAL_MAX_PIXELS):
      return reverse('content:thumbnail', args=[self.token, 'xlarge'])
    return reverse('content:file', args=[self.token])

  def get_list_url(self):
    """Where to go when this item is gone for the viewer (set to deleted
    in edit mode - cmnsd object_form)."""
    return reverse('content:list')

  @property
  def sub_kind_display(self):
    """The detail's photo_kind / document_kind label - '' if none, and ''
    for 'other': a label that only says "other" adds nothing next to the
    kind (most imported photos are 'other')."""
    detail = self.get_detail()
    for field in ('photo_kind', 'document_kind'):
      if detail is not None and hasattr(detail, field):
        if getattr(detail, field) == 'other':
          return ''
        return getattr(detail, f'get_{field}_display')()
    return ''

  # SlugMixin
  @classmethod
  def api_search_q(cls, term, request=None):
    """Extra free-text search (cmnsd.api.filtering - the content list, the
    picker, /search/): the text of its transcripts, and of its parts' -
    only parts this viewer may see, so a hidden page's text can't make its
    book show up - and a book's author as written on it. A transcript is
    as visible as its item, so the item's own visibility covers it."""
    in_text = models.Q(transcripts__text__icontains=term)
    parts = Content.objects.visible_to(request).filter(in_text)
    return in_text | models.Q(parts__in=parts) | models.Q(book_detail__author__icontains=term)

  def get_slug_source(self):
    if self.name:
      return self.name
    if self.original_filename and not is_meaningless_filename(self.original_filename):
      return split_filename(self.original_filename)[0]
    return self.token

  def is_accessible_to(self, user):
    """Status + visibility for one loaded object, in Python - mirrors
    StatusMixin.filter_status() and VisibilityMixin.filter_visibility(),
    which the views use as queryset filters. For rendering decisions on
    already-loaded content (an avatar), where a query per item would be
    wasteful."""
    authenticated = bool(user and user.is_authenticated)
    return self.is_status_visible_to(user) and self.is_visible_to(user if authenticated else None)

  @property
  def media_type(self):
    """image / pdf / audio / video / other - from the file, not the kind."""
    mimetype = mimetypes.guess_type(self.file.name or self.original_filename)[0] or ''
    if mimetype == 'application/pdf':
      return 'pdf'
    major = mimetype.split('/')[0]
    return major if major in ('image', 'audio', 'video') else 'other'

  def get_detail(self):
    return getattr(self, f"{self.kind}_detail", None)

  def ensure_detail(self):
    """Create the detail row for this kind, if the kind has one and it's
    missing. A detail from a previous kind is kept, not deleted - switching
    kind back doesn't lose what was filled in."""
    from .details import DETAIL_MODELS
    model = DETAIL_MODELS.get(self.kind)
    if model and self.get_detail() is None:
      model.objects.create(content=self)

  @property
  def thumb_crop_box(self):
    """(x, y, w, h) fractions of the thumbnail crop, or None."""
    values = (self.thumb_crop_x, self.thumb_crop_y, self.thumb_crop_w, self.thumb_crop_h)
    return None if any(v is None for v in values) else values

  @property
  def thumb_version(self):
    """Changes with the thumbnail crop - appended to the thumbnail URL
    (content_tags.thumb_url) so a browser doesn't keep the previous one."""
    box = self.thumb_crop_box
    if box is None and not self.thumb_rotation:
      return ''
    crop = '-'.join(f'{v:.4f}' for v in box) if box else 'full'
    return f'{crop}-r{self.thumb_rotation}' if self.thumb_rotation else crop

  def clean(self):
    """Parts are one level deep: a part can't have parts of its own, and
    an item with parts can't become a part - so "the whole" is never
    ambiguous. Checked by the admin (form clean) and make_parts_of().
    The partial date's own rules first (PartialDateMixin.clean)."""
    super().clean()
    values = (self.thumb_crop_x, self.thumb_crop_y, self.thumb_crop_w, self.thumb_crop_h)
    if any(v is not None for v in values) and self.thumb_crop_box is None:
      raise ValidationError(_("Set all four crop values, or none."))
    box = self.thumb_crop_box
    if box and (box[0] + box[2] > 1.0001 or box[1] + box[3] > 1.0001):
      raise ValidationError(_("The crop must lie within the image."))
    if self.parent_id:
      if self.parent_id == self.pk:
        raise ValidationError({'parent': _("An item can't be a part of itself.")})
      if self.parent.parent_id:
        raise ValidationError({'parent': _("That item is itself a part - choose its whole instead.")})
      if self.pk and self.parts.exists():
        raise ValidationError({'parent': _("This item has parts of its own, so it can't become a part.")})

  def make_parts_of(self, parts):
    """Make `parts` (Content items) parts of this item, numbered 1, 2, ...
    in the given order - adjust afterwards: position 0 = a variant of this
    item (e.g. a colorized version), the same number twice = variants of
    each other. Validates the one-level rule first; nothing changes if any
    item fails."""
    parts = [part for part in parts if part.pk != self.pk]
    if self.parent_id:
      raise ValidationError(_("%(item)s is itself a part - choose its whole instead.") % {'item': self})
    for part in parts:
      part.parent = self
      part.clean()
    for position, part in enumerate(parts, start=1):
      type(part).objects.filter(pk=part.pk).update(parent=self, position=position)
    return len(parts)

  # --- Parts, edited on the page (edit mode) - logic in content/parts.py.
  # Each returns nothing to render: the page reloads (the gallery, the
  # parts row and "part n of m" all depend on the order).

  def _content_from(self, request, data):
    """The item named by data['token'] - only one this viewer may see."""
    item = Content.objects.visible_to(request).filter(token=data.get('token') or '').first()
    if item is None:
      raise ValidationError(gettext("That item wasn't found."))
    return item

  @api_action()
  def set_portrait(self, request, data):
    """data: {token} - this photo becomes that person's portrait
    (content/portraits.py)."""
    from ..portraits import set_portrait
    return set_portrait(self, data.get('token'), request)

  @api_action()
  def add_part(self, request, data):
    """data: {token} - make that item the last part of this one."""
    from ..parts import add_part
    add_part(self, self._content_from(request, data), request)
    return {}

  @api_action()
  def move_part(self, request, data):
    """data: {direction: 'earlier' | 'later'} - this part, with its variants."""
    from ..parts import move_part
    move_part(self, data.get('direction'), request)
    return {}

  @api_action()
  def toggle_variant(self, request, data):
    from ..parts import toggle_variant
    toggle_variant(self, request)
    return {}

  @api_action()
  def join_previous(self, request, data):
    from ..parts import join_previous
    join_previous(self, request)
    return {}

  @api_action()
  def separate_part(self, request, data):
    from ..parts import separate_part
    separate_part(self, request)
    return {}

  @api_action()
  def detach_part(self, request, data):
    from ..parts import detach_part
    detach_part(self, request)
    return {}

  def save(self, *args, **kwargs):
    # Before the slug is generated (SlugMixin) and before upload_to runs, so
    # an unnamed upload's slug can come from its (meaningful) filename.
    new_file = bool(self.file) and not self.file._committed
    if new_file and not self.original_filename:
      self.original_filename = os.path.basename(self.file.name)
    super().save(*args, **kwargs)
    self.ensure_detail()
    self.sync_filename()
    if new_file or self.width is None:
      self.measure()

  def measure(self):
    """Store the image's width and height (as shown) - header only, no
    decode; None for anything that isn't an image or can't be read.
    Saved with update(), not save(): nothing else changes."""
    from ..crop import displayed_size
    size = (None, None)
    if self.file and self.media_type == 'image':
      try:
        size = displayed_size(self.file.path)
      except (OSError, ValueError, SyntaxError):
        pass
    if (self.width, self.height) != size:
      self.width, self.height = size
      type(self).objects.filter(pk=self.pk).update(width=self.width, height=self.height)

  def sync_filename(self):
    """Rename the stored file to what it should be called now: after the
    slug if its original name was meaningless, otherwise that original name
    (content/files.py). A no-op when it already is, or there's no file.
    Returns True if the file was renamed. Runs on every save; call it
    directly to fix a backlog (e.g. after an import)."""
    return rename_content_file(self)
