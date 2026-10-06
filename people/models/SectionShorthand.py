from django.db import models
from django.db.models import Prefetch, Q

from cmnsd.api.registry import api_field


class SectionShorthand(models.Model):
  """
  The person page's collapsible sections (cmnsd/section.html): what each
  one shows, as @api_field methods - so a closed section can be rendered
  on demand through the API (person/functions/<method>.html) - plus a
  cheap count per section for its header, which is all a closed section
  costs.

  Every method takes the request: what's shown depends on the viewer.
  """

  class Meta:
    abstract = True

  # --- Relationships --------------------------------------------------------

  @api_field(readonly=True)
  def get_relationships(self, request=None):
    """Rendered by person/functions/get_relationships.html (parents,
    siblings, partners, children). The value itself is the row count."""
    return self.count_relationships(request)

  def count_relationships(self, request=None):
    """Rows the Relationships section shows for this viewer, without
    building them: 4 light queries instead of the full section's family
    walk, lifespans and portraits. Same rules as the rows - deleted people
    dropped (FamilyShorthand._drop_deleted), concept/revoked only if this
    viewer may see them (status_visible_to); a deleted parent also drops
    the siblings through them."""
    from .PersonRelations import PersonRelation
    PARENT, PARTNER = PersonRelation.RelationType.PARENT, PersonRelation.RelationType.PARTNER
    relations = PersonRelation.objects.filter(Q(person_from=self) | Q(person_to=self)).values_list(
      'person_from', 'person_to', 'relation_type',
    )
    parents = {a for a, b, kind in relations if kind == PARENT and b == self.pk}
    children = {b for a, b, kind in relations if kind == PARENT and a == self.pk}
    partners = {b if a == self.pk else a for a, b, kind in relations if kind == PARTNER}

    people = {p.pk: p for p in self.__class__.objects.filter(pk__in=parents).only('pk', 'status', 'user')}
    parents = {pk for pk in parents if pk in people and people[pk].status != self.Status.DELETED}
    siblings = set(PersonRelation.objects.filter(
      relation_type=PARENT, person_from__in=parents,
    ).exclude(person_to=self).values_list('person_to', flat=True))

    everyone = parents | children | partners | siblings
    people = {p.pk: p for p in self.__class__.objects.filter(pk__in=everyone).only('pk', 'status', 'user')}
    user = getattr(request, 'user', None)
    shown = lambda ids: sum(1 for pk in ids if pk in people and people[pk].is_status_visible_to(user))
    return shown(parents) + shown(siblings) + shown(partners) + shown(children)

  # --- Content --------------------------------------------------------------

  def _visible_content(self, request):
    """Content linked to this person (Content.people) plus books they wrote
    (BookContent.authors) - the same item once, even if both. Parts are
    never listed on their own, so someone linked only to a part (the back
    of a postcard) gets the whole it belongs to."""
    from content.models import Content
    return Content.objects.visible_to(request).listable().filter(
      Q(people=self) | Q(book_detail__authors=self) | Q(parts__people=self),
    ).distinct()

  @api_field(readonly=True)
  def get_visible_content(self, request=None):
    """The content linked to this person that this viewer may see: books
    but not their parts, detail rows included for the kind labels. In the
    viewer's remembered order (content_sort()): most recently added first
    by default - it shows how the research on this person grew (imported
    items keep the date they were added to the old site) - or
    chronologically, by the item's own date, undated last. Rendered by
    person/functions/get_visible_content.html."""
    queryset = self._visible_content(request).select_related('photo_detail', 'document_detail', 'book_detail')
    items = list(queryset.in_order(self.content_sort(request)))
    # Mark what they wrote, so the card can say "author" - "wrote this" is
    # not the same as "is in it".
    authored = set(self.authored_books.values_list('content_id', flat=True))
    for item in items:
      item.by_this_person = item.pk in authored
    return items

  CONTENT_SORTS = ('added', 'date')

  def content_sort(self, request=None):
    """'added' (default) or 'date' - the viewer's remembered order for the
    Content section, the same on every person page (cmnsd/ui/state.py)."""
    from cmnsd.ui.state import get_sort
    return get_sort(request, 'person.content', 'added', self.CONTENT_SORTS)

  def count_visible_content(self, request=None):
    return self._visible_content(request).count()

  # --- Events ---------------------------------------------------------------

  @api_field(readonly=True)
  def get_visible_events(self, request=None):
    """This person's events, each with the content documenting it that this
    viewer may see (event.visible_content) - one query for all events.
    Rendered by person/functions/get_visible_events.html."""
    from content.models import Content
    return self.events.current().prefetch_related(
      Prefetch('content', queryset=Content.objects.visible_to(request), to_attr='visible_content'),
    )

  def count_visible_events(self, request=None):
    """Their own events as the timeline shows them: dated, or their
    birth or death (people/timeline.py _placed)."""
    from django.db.models import Q
    from events.models import Event
    return self.events.current().filter(Q(year__isnull=False) | Q(kind__in=[Event.Kind.BIRTH, Event.Kind.DEATH])).count()

  # --- Comments -------------------------------------------------------------

  @api_field(readonly=True)
  def get_comments(self, request=None):
    """The comments this viewer may see (CommentableMixin). Rendered by
    person/functions/get_comments.html - the thread plus, signed in, the
    form (add_comment through the API)."""
    return self.get_visible_comments(request)

  def count_comments(self, request=None):
    return self.get_visible_comments(request).count()
