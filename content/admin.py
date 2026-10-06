from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import ValidationError
from django.shortcuts import render

from cmnsd.admin.mixins import (
  TimestampAdminMixin, StatusAdminMixin, VisibilityAdminMixin, OwnershipAdminMixin,
)
from .models import BookContent, Content, DocumentContent, PhotoContent, Portrait, Transcript


class PhotoContentInline(admin.StackedInline):
  model = PhotoContent
  can_delete = False


class DocumentContentInline(admin.StackedInline):
  model = DocumentContent
  can_delete = False


class BookContentInline(admin.StackedInline):
  model = BookContent
  can_delete = False
  autocomplete_fields = ('authors',)
  fields = ('authors', 'author', 'publisher', 'isbn')


class TranscriptInline(admin.StackedInline):
  """What's written on the item, and translations of it (content.Transcript)."""
  model = Transcript
  extra = 0
  fields = ('kind', 'language', 'method', 'text')


class PortraitInline(admin.TabularInline):
  model = Portrait
  extra = 0
  raw_id_fields = ('person',)


class PartInline(admin.TabularInline):
  """Parts of this item, in order: position 1, 2, ... - a postcard's back,
  a book's pages, the other photos of one moment. Position 0 = a variant
  of this item itself (a colorized version); the same number twice =
  variants of each other."""
  model = Content
  fk_name = 'parent'
  extra = 0
  fields = ('position', 'name', 'kind', 'file')
  show_change_link = True
  verbose_name = "part"
  verbose_name_plural = "parts"


@admin.register(Content)
class ContentAdmin(
  TimestampAdminMixin, StatusAdminMixin, VisibilityAdminMixin, OwnershipAdminMixin,
  admin.ModelAdmin,
):
  list_display = ('name', 'kind', 'stored_filename', 'original_filename', 'status', 'visibility')
  list_filter = ('kind',)
  search_fields = ('name', 'description', 'original_filename', 'source')
  readonly_fields = ('slug', 'original_filename', 'stored_filename')
  raw_id_fields = ('parent',)
  filter_horizontal = ('people', 'tags', 'places', 'events')
  actions = [
    'mark_status_c', 'mark_status_p', 'mark_status_r', 'mark_status_x',
    'mark_visibility_p', 'mark_visibility_c', 'mark_visibility_f', 'mark_visibility_q',
    'give_useful_filename', 'move_description_to_transcript', 'make_parts',
  ]

  @admin.display(description="stored as")
  def stored_filename(self, obj):
    return obj.file.name.rsplit('/', 1)[-1] if obj.file else '-'

  @admin.action(description="Give files a useful name")
  def give_useful_filename(self, request, queryset):
    """Content.sync_filename() on each selected item: a file whose original
    name is meaningless (IMG_1234, 2023-12-10-IMG_1234, a UUID, ...) is
    renamed after the item's name; a meaningful name is left alone. Saving
    an item does this too - this is for the backlog."""
    renamed = sum(content.sync_filename() for content in queryset)
    self.message_user(request, f"{renamed} of {queryset.count()} file(s) renamed; the rest already had a useful name.")

  # Only the inline for this item's kind - a photo has no book fields.
  _DETAIL_INLINES = {'photo': PhotoContentInline, 'document': DocumentContentInline, 'book': BookContentInline}

  @admin.action(description="Move description to transcript")
  def move_description_to_transcript(self, request, queryset):
    """For items whose description is really the text written on them (a
    transcription): the description becomes the original transcript -
    typed by hand, in the document's language, else Dutch - and the
    description is emptied. Skips items without a description or that
    already have an original transcript. Only what you select: legacy
    descriptions are mostly commentary, not transcriptions."""
    moved = skipped = 0
    for content in queryset:
      if not content.description.strip() or content.transcripts.filter(kind=Transcript.Kind.ORIGINAL).exists():
        skipped += 1
        continue
      detail = content.get_detail()
      language = getattr(detail, 'language', '') or 'nl'
      Transcript.objects.create(
        content=content, kind=Transcript.Kind.ORIGINAL, language=language,
        method=Transcript.Method.MANUAL, text=content.description,
      )
      content.description = ''
      content.save()
      moved += 1
    self.message_user(request, f"{moved} description(s) moved to a transcript; {skipped} skipped (no description, or already an original transcript).")

  def get_inlines(self, request, obj):
    # The kind's own fields (book authors, document kind + language, photo
    # kind) first, right under the main form - then transcripts etc.
    inlines = []
    if obj and obj.kind in self._DETAIL_INLINES:
      inlines.append(self._DETAIL_INLINES[obj.kind])
    if obj:
      inlines.append(TranscriptInline)
    if obj and obj.kind == Content.Kind.PHOTO:
      inlines.append(PortraitInline)
    # Parts for every kind - but not on an item that is itself a part
    # (one level deep, see Content.clean).
    if obj and not obj.parent_id:
      inlines.append(PartInline)
    return inlines

  @admin.action(description="Make parts of…")
  def make_parts(self, request, queryset):
    """Select the items that belong together, then choose which one is the
    whole: the others become its parts, numbered 1, 2, ... in the order
    shown (by name) - adjust the numbers afterwards on the whole's page
    (0 = a variant of the whole). A confirmation page first."""
    items = list(queryset.order_by('name', 'pk'))
    if len(items) < 2:
      self.message_user(request, "Select at least two items: a whole and its part(s).", messages.WARNING)
      return None
    if request.POST.get('apply'):
      lead = next((item for item in items if str(item.pk) == request.POST.get('lead')), None)
      if lead is None:
        self.message_user(request, "Choose which item is the whole.", messages.WARNING)
        return None
      try:
        count = lead.make_parts_of([item for item in items if item.pk != lead.pk])
      except ValidationError as error:
        self.message_user(request, ' '.join(error.messages), messages.ERROR)
        return None
      self.message_user(request, f"{count} item(s) are now parts of “{lead}”, numbered 1-{count}.")
      return None
    return render(request, 'admin/content/content/make_parts.html', {
      **self.admin_site.each_context(request),
      'title': "Make parts of…",
      'items': items,
      'opts': self.model._meta,
      'action_checkbox_name': helpers.ACTION_CHECKBOX_NAME,
    })
