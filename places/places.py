"""
Places with how much this viewer may see there - for the places overview
(/places/) and a place's own page: the content items (wholes, an item
counted once - also when it's there because one of its parts is) and the
events (only visible ones: an event is visible through its people).

Counts are a place's own, not its sub-places': Java's count doesn't
include Batavia's. Three queries for any number of places.
"""

from collections import defaultdict

from cmnsd.models.access import filter_accessible

from django.utils.translation import gettext as _

from .models import Place


def attach_counts(places, request):
  """Set place.content_count, .event_count and .count (both) on each of
  `places`; returns them as a list."""
  from content.models import Content
  from events.models import Event
  places = list(places)
  ids = [place.pk for place in places]
  wholes = Content.objects.visible_to(request).listable()
  items, events = defaultdict(set), defaultdict(set)
  for place_id, content_id in wholes.filter(places__in=ids).values_list('places', 'pk'):
    items[place_id].add(content_id)
  for place_id, content_id in wholes.filter(parts__places__in=ids).values_list('parts__places', 'pk'):
    items[place_id].add(content_id)
  for place_id, event_id in filter_accessible(Event.objects.all(), request).filter(places__in=ids).values_list('places', 'pk'):
    events[place_id].add(event_id)
  for place in places:
    place.content_count = len(items[place.pk])
    place.event_count = len(events[place.pk])
    place.count = place.content_count + place.event_count
  return places


def descendant_tokens(place):
  """The tokens of every place within `place`, any depth - one query per
  level."""
  tokens, level = [], [place.pk]
  while level:
    rows = list(Place.objects.filter(parent__in=level).values_list('pk', 'token'))
    tokens += [token for _pk, token in rows]
    level = [pk for pk, _token in rows]
  return tokens


def _by_name(place):
  return place.name.casefold()


def _tree(places, root_id, show_all):
  """The places directly under root_id (None: the top level) that are
  listed - each with .listed_children, any depth, by name. Listed: something
  is there for this viewer, or in a sub-place - or show_all."""
  children = defaultdict(list)
  for place in places:
    children[place.parent_id].append(place)

  def build(place):
    place.listed_children = sorted(filter(None, (build(child) for child in children[place.pk])), key=_by_name)
    if show_all or place.count or place.listed_children:
      return place
    return None

  return sorted(filter(None, (build(place) for place in children[root_id])), key=_by_name)


def place_tree(request, show_all=False):
  """The places as a tree, for /places/: the top-level places (countries,
  regions without a parent) with their sub-places. show_all (edit mode):
  every place, so the empty ones can be put in order too."""
  return _tree(attach_counts(Place.objects.all(), request), None, show_all)


def sub_places(place, request, show_all=False):
  """The places within `place`, as a tree - for its page."""
  within = Place.objects.filter(token__in=descendant_tokens(place))
  return _tree(attach_counts(within, request), place.pk, show_all)


def picked_place(form, field='place'):
  """For a form with a place picker (cmnsd PickerInput with create_label):
  call from clean(). The place chosen, or - a name typed with "+ create" -
  the existing place of that name (several: a form error - choose one),
  else a new one remembered for create_picked_place() at save time. Creating needs places.add_place
  (a form error otherwise)."""
  from cmnsd.forms.widgets import PickerInput
  place = form.cleaned_data.get(field)
  name = PickerInput.new_name(form, field)
  form._new_place_name = ''
  form._picked_by_name = None
  if place or not name:
    return place
  existing = list(Place.objects.filter(name__iexact=name)[:2])
  if len(existing) == 2:
    # e.g. two places called Java - which one isn't for us to guess.
    form.add_error(field, _("There are several places called “%(name)s” - choose one from the list.") % {'name': name})
    return None
  if existing:
    form.cleaned_data[field] = form._picked_by_name = existing[0]
    return existing[0]
  user = getattr(getattr(form, 'request', None), 'user', None)
  if not (user and user.has_perm('places.add_place')):
    form.add_error(field, _("You may not add a place."))
    return None
  form._new_place_name = name
  return None


def create_picked_place(form, field='place'):
  """At save time: the place picked_place() left to create (or the chosen
  one) - owned by the user, logged to the admin history."""
  from django.contrib.admin.models import ADDITION, LogEntry
  name = getattr(form, '_new_place_name', '')
  if not name:
    return form.cleaned_data.get(field)
  place = Place(name=name, user=form.request.user)
  place.save()
  LogEntry.objects.log_actions(form.request.user.pk, [place], ADDITION, change_message="Created while editing", single_object=True)
  return place
