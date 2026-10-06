from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import DetailView

from cmnsd.edit.mode import can_edit, is_edit_mode
from cmnsd.models.access import filter_accessible
from cmnsd.views.mixins import VisibilityViewMixin

from core.tags import attach_content_counts, by_count
from people.models import Person

from ..models import Content


class ContentDetailView(VisibilityViewMixin, DetailView):
  """content/<token>/ - one item, shown by its media type (image, PDF,
  audio, video), with its description, date, source, people, tags and
  places; a book also shows its parts in order. Hidden and nonexistent
  both 404 (the queryset is visibility-filtered)."""
  model = Content
  slug_field = 'token'
  slug_url_kwarg = 'token'
  context_object_name = 'content'
  template_name = 'content/content_detail.html'

  def get(self, request, *args, **kwargs):
    """Found by token (get_queryset is visibility-filtered, so a hidden
    item 404s before anything else). If the URL's slug is missing or
    outdated, redirect to the current one - only after that check, so a
    redirect never reveals a hidden item's name."""
    self.object = self.get_object()
    # The slug the address should carry: none while the item has no name
    # (Content.has_readable_slug).
    wanted = self.object.slug if self.object.has_readable_slug else None
    if kwargs.get('slug') != wanted:
      # Keep the query (?open=..., ?left=...): it's meant for the page.
      url, query = self.object.get_absolute_url(), request.GET.urlencode()
      return redirect(f'{url}?{query}' if query else url, permanent=True)
    context = self.get_context_data(object=self.object)
    return self.render_to_response(context)

  def get_queryset(self):
    # Status and visibility - and for staff a deleted item too, marked as
    # such (Content.objects.viewable_by).
    return Content.objects.viewable_by(self.request).select_related(
      'photo_detail', 'document_detail', 'book_detail', 'parent', 'user__person',
    )

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    content = self.object
    people = filter_accessible(content.people.all(), self.request)
    # Rows render lifespan + avatar: batch both, not a query per person.
    context['visible_people'] = Person._attach_portraits(Person._attach_lifespan(people))
    # With their content counts: how much a tag groups shows how important it is.
    context['visible_tags'] = by_count(attach_content_counts(filter_accessible(content.tags.all(), self.request), self.request))
    context['places'] = list(content.places.select_related('parent__parent'))
    context['transcripts'] = list(content.transcripts.all())
    # Transcription still to do - none yet, one incomplete, or an automatic
    # one not checked: then the item page offers the transcribe page also
    # outside edit mode (in edit mode it always does).
    context['transcription_open'] = not context['transcripts'] or any(
      t.incomplete or t.is_unchecked for t in context['transcripts']
    )
    # Visible when at least one of its people is (Event.filter_visibility);
    # shown with event_display, hidden people obfuscated.
    context['events'] = list(filter_accessible(content.events.all(), self.request).prefetch_related('people', 'places'))
    # Parts in order; position 0 = variants of this item itself (shown with
    # it, e.g. the colorized version), 1, 2, ... = the next parts - the
    # same number twice = variants of each other, side by side.
    parts = list(content.parts.visible_to(self.request).order_by('position', 'pk'))
    context['variants'] = [part for part in parts if part.position == 0]
    context['parts'] = [part for part in parts if part.position != 0]
    parent = content.parent
    context['parent'] = parent if parent and Content.objects.visible_to(self.request).filter(pk=parent.pk).exists() else None

    # The whole group this item belongs to - the whole, then its variants
    # and parts in order - shown as numbered thumbnails on the whole's page
    # and on each part's page (the current one marked). Counted as one
    # group: a book with 6 pages is 7.
    whole = context['parent'] or (content if parts else None)
    group = []
    if whole is not None:
      whole_parts = parts if whole is content else list(whole.parts.visible_to(self.request).order_by('position', 'pk'))
      group = [whole, *whole_parts]
    context['group'] = group

    # Browsing on the whole's page (cmnsd.js gallery.js): the group's
    # images in that order - only when the whole is itself an image.
    gallery = []
    if whole is content and content.file and content.media_type == 'image':
      gallery = [self._gallery_item(item) for item in group if item.file and item.media_type == 'image']
    context['gallery'] = gallery if len(gallery) > 1 else []
    context['gallery_index'] = {item['token']: index for index, item in enumerate(context['gallery'])}

    # A draft of yours: it's in your inbox - and the next one there.
    if content.status == Content.Status.CONCEPT and content.user_id == self.request.user.pk:
      from .upload import inbox_items, inbox_order
      drafts = inbox_order(inbox_items(self.request.user).only('pk', 'token', 'slug', 'date_created', 'original_filename', 'name'))
      index = next((i for i, draft in enumerate(drafts) if draft.pk == content.pk), None)
      context['inbox_count'] = len(drafts)
      if index is not None and index + 1 < len(drafts):
        context['inbox_next'] = drafts[index + 1]

    self._edit_parts_context(context, content, whole, group)
    # Edit mode: chips with "×" and a picker per relation (cmnsd
    # EditableRelationsMixin; content/_tag_chip.html).
    context['edit_relations'] = is_edit_mode(self.request) and can_edit(content, self.request.user)
    # "+ new event" starts on this item's date (a clipping: when it was
    # published - often just after the event; changeable in the dialog,
    # nothing stays tied to the item). The event form reads its initial
    # values from the address (cmnsd object_create).
    from urllib.parse import urlencode
    date = {name: getattr(content, name) for name in ('year', 'month', 'day') if getattr(content, name)}
    if date:
      date['date_qualifier'] = content.date_qualifier
    context['new_event_query'] = f'?{urlencode(date)}' if date else ''
    # A deleted item (only staff get here) is opened to be checked: every
    # section open, whatever is remembered (cmnsd/section.html).
    context['unfold_sections'] = content.status == Content.Status.DELETED
    context['tag_tokens'] = ','.join(tag.token for tag in context['visible_tags'])
    context['person_tokens'] = ','.join(person.token for person in context['visible_people'])
    context['place_tokens'] = ','.join(place.token for place in context['places'])
    context['event_tokens'] = ','.join(event.token for event in context['events'])
    book = getattr(content, 'book_detail', None) if content.kind == 'book' else None
    context['author_tokens'] = ','.join(author.token for author in book.authors.all()) if book else ''

    # On a part's page: its place among its siblings, with previous/next.
    if context['parent']:
      siblings = list(context['parent'].parts.visible_to(self.request).order_by('position', 'pk'))
      index = next((i for i, sibling in enumerate(siblings) if sibling.pk == content.pk), None)
      if index is not None:
        context['sibling_index'] = index + 1
        context['sibling_count'] = len(siblings)
        context['previous_part'] = siblings[index - 1] if index > 0 else None
        context['next_part'] = siblings[index + 1] if index + 1 < len(siblings) else None
    return context

  def _edit_parts_context(self, context, content, whole, group):
    """Edit mode (cmnsd/edit/mode.py), for someone who may change this
    item: the parts editor (content/_parts_edit.html) - which item is the
    whole (parts are always added to the whole), and per part which moves
    make sense: earlier/later between number groups, join the previous
    number or take its own again. Not when this is a part whose whole the
    viewer can't see."""
    request = self.request
    editable = is_edit_mode(request) and can_edit(content, request.user)
    if content.parent_id and context['parent'] is None:
      editable = False
    context['edit_parts'] = editable
    if not editable:
      return
    target = whole or content
    parts = [part for part in group if part.pk != target.pk]
    numbers = sorted({part.position for part in parts if part.position})
    for part in parts:
      shared = sum(1 for other in parts if other.position == part.position) > 1
      part.edit_is_variant = part.position == 0
      part.edit_first = not part.position or part.position == numbers[0]
      part.edit_last = not part.position or part.position == numbers[-1]
      part.edit_shared = bool(part.position) and shared
    context['parts_whole'] = target
    context['edit_part_rows'] = parts
    # "Make this a part of..." - only for an item that is neither a part nor
    # a whole with parts (one level deep).
    context['can_become_part'] = not content.parent_id and not parts

  @staticmethod
  def _gallery_item(item):
    return {
      'token': item.token,
      'title': str(item),
      'src': reverse('content:thumbnail', args=[item.token, 'large']),
      'file': reverse('content:file', args=[item.token]),
      'zoom': item.zoom_url(),   # sharper, when zoomed in (lightbox)
      'page': item.get_absolute_url(),
    }
