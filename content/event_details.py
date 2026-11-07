"""An item's date and places from an event it documents - offered, never
set by itself: a wedding photo has the wedding's date, an announcement
comes days later, a certificate maybe years, an address book has its
edition's year. One click copies it; it stays the item's own, to change.
Offered while the item has none of it yet (Content.use_event_detail, the
item's page in edit mode)."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

from cmnsd.edit.log import log_change
from cmnsd.edit.mode import require_can_edit

DATE_FIELDS = ('year', 'month', 'day', 'date_qualifier')


def event_offers(content, events):
  """Per linked event (events: the ones this viewer may see), what it
  could give the item: [(event, date, places)] - date its display ('' if
  the item has a date already, or the event none), places a list (empty
  if the item has places already). Events with nothing to give left out."""
  dated = bool(content.year)
  placed = content.places.exists()
  offers = []
  for event in events:
    date = '' if dated else event.partial_date_display()
    places = [] if placed else list(event.places.all())
    if date or places:
      offers.append((event, date, places))
  return offers


def use_event_detail(content, data, request):
  """data: {event: token, part: 'date' | 'places'} - that event's date (with
  how sure it is) or places onto this item. Only an event linked to it and
  visible to this viewer; only while the item has none of that part."""
  from cmnsd.models.access import filter_accessible
  require_can_edit(content, request)
  event = filter_accessible(content.events.all(), request).filter(token=data.get('event') or '').first()
  if event is None:
    raise ValidationError(_("That event isn't linked to this item."))
  part = data.get('part')
  if part == 'date':
    if content.year:
      raise ValidationError(_("This item has a date already - change it there."))
    if not event.year:
      raise ValidationError(_("That event has no date."))
    for name in DATE_FIELDS:
      setattr(content, name, getattr(event, name))
    content.save(update_fields=[*DATE_FIELDS, 'date_modified'])
    log_change(request, content, f"Date from the event {event}: {content.partial_date_display()}")
    messages.success(request, _("Date set: %(date)s.") % {'date': content.partial_date_display()})
  elif part == 'places':
    if content.places.exists():
      raise ValidationError(_("This item has places already - add more there."))
    places = list(event.places.all())
    if not places:
      raise ValidationError(_("That event has no places."))
    content.places.add(*places)
    names = ', '.join(place.name for place in places)
    log_change(request, content, f"Places from the event {event}: {names}")
    messages.success(request, _("Places set: %(places)s.") % {'places': names})
  else:
    raise ValidationError(_("Choose the date or the places."))
  return {}
