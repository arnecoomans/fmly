"""
Anniversaries: events by day of the year, across the years - every kind
with a known day (births, marriages, deaths, migrations, history ...) - for
the dashboard's "on this day" and the calendar (events/calendar/). Only
what the viewer may see. A living person's birthday (their date of birth)
only for someone signed in - a family member; signed out, a birth only of
someone who has died.
"""

from django.db.models import Q

from cmnsd.models.access import filter_accessible

from .models import Event

def shown(event, request=None):
  """Every event; a birth for a signed-in viewer (who may see the person -
  the queryset decided that), else only of someone who has died."""
  if event.kind != Event.Kind.BIRTH or (request is not None and request.user.is_authenticated):
    return True
  return all(person.death for person in event.people.all())


def anniversaries(request, days=None, month=None):
  """The events on these days (dates: month and day count, the
  year doesn't) - or, with `month`, every day of that month - by day, then
  year."""
  events = filter_accessible(Event.objects.all(), request).filter(day__isnull=False, month__isnull=False)
  if month:
    events = events.filter(month=month)
  else:
    q = Q(pk__in=[])
    for day in days:
      q |= Q(month=day.month, day=day.day)
    events = events.filter(q)
  events = events.prefetch_related('people', 'places__parent').order_by('month', 'day', 'year', 'pk')
  from people.models import Person
  events = list(events)
  # Whether each person has died (shown): their deaths in one query.
  Person._attach_lifespan([p for e in events if e.kind == Event.Kind.BIRTH for p in e.people.all()])
  events = [event for event in events if shown(event, request)]
  if days:
    # In the order of the days asked for - the coming week can run into January.
    order = {(day.month, day.day): index for index, day in enumerate(days)}
    events.sort(key=lambda event: (order.get((event.month, event.day), 0), event.year or 0))
  return events
