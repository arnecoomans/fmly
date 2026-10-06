from collections import Counter

from django.db.models import Count, Prefetch
from django.utils.translation import gettext_lazy as _
from django.views.generic import TemplateView

from cmnsd.models.access import filter_accessible

from ..models import Event

# The pills: what the page shows (?kind=). Historical by default - the
# history the family's lives took place in; 'all' is a family chronicle.
KINDS = (
  ('historical', _("historical")),
  ('all', _("all")),
  ('birth', _("births")),
  ('marriage', _("marriages")),
  ('migration', _("migrations")),
  ('death', _("deaths")),
  ('other', _("other")),
)


class EventListView(TemplateView):
  """/events/ - events by decade, oldest first: historical events by
  default (a general event without people has no page of its own - this
  is where it lives), ?kind= for another kind or 'all' (a chronicle of
  the family: what happened when, across every branch). Undated ones last.
  Only what this viewer may see: an event through its people (a historical
  one, without people, is visible to all). Each as event/_event.html."""
  template_name = 'event/event_overview.html'

  def get_context_data(self, **kwargs):
    from content.models import Content
    context = super().get_context_data(**kwargs)
    kind = self.request.GET.get('kind') or 'historical'
    if kind not in dict(KINDS):
      kind = 'historical'
    visible = filter_accessible(Event.objects.all(), self.request)
    # Distinct events per kind: the visibility filter joins the people.
    counts = Counter(dict(
      Event.objects.filter(pk__in=visible.values('pk')).values_list('kind').annotate(n=Count('pk')).values_list('kind', 'n')
    ))
    events = visible if kind == 'all' else visible.filter(kind=kind)
    events = list(events.prefetch_related(
      'people', 'places__parent__parent',
      Prefetch('content', queryset=Content.objects.visible_to(self.request), to_attr='visible_content'),
    ).order_by('year', 'month', 'day', 'pk'))

    # A marriage shows each spouse's age then (event/_event.html): their
    # births in one query, not one per spouse.
    from people.models import Person
    Person._attach_lifespan([person for event in events if event.kind == Event.Kind.MARRIAGE for person in event.people.all()])

    decades = {}
    undated = []
    for event in events:
      if event.year:
        decades.setdefault(event.year // 10 * 10, []).append(event)
      else:
        undated.append(event)
    context.update({
      'kind': kind,
      'kinds': [(value, label, sum(counts.values()) if value == 'all' else counts[value]) for value, label in KINDS],
      'decades': sorted(decades.items()),
      'undated': undated,
      'total': len(events),
    })
    return context
