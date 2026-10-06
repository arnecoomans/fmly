from django.db.models import Q
from django.shortcuts import redirect
from django.views.generic import DetailView

from cmnsd.edit.mode import can_edit, is_edit_mode
from cmnsd.models.access import filter_accessible
from cmnsd.ui.state import get_sort

from ..models import Place
from ..places import attach_counts, sub_places


class PlaceDetailView(DetailView):
  """places/<token>/<slug>/ - a place's page: where it lies (its parents),
  its name, other spelling and description; the same place in another era
  (alternatives); the places within it; its events and its content (the
  shared content grid, remembered sort - key 'place.content').

  Places have no status or visibility - anyone may open one - but what's
  shown there is only what this viewer may see: content by its status and
  visibility, events through their people (named as the viewer may see
  them). In edit mode, for someone with places.change_place, the blocks
  and the alternatives are editable."""
  model = Place
  slug_field = 'token'
  slug_url_kwarg = 'token'
  context_object_name = 'place'
  template_name = 'place/place_detail.html'
  SORTS = ('added', 'date')

  def get_queryset(self):
    return Place.objects.select_related('parent')

  def get(self, request, *args, **kwargs):
    self.object = self.get_object()
    if kwargs.get('slug') != self.object.slug and self.object.slug:
      return redirect(self.object.get_absolute_url(), permanent=True)
    return self.render_to_response(self.get_context_data(object=self.object))

  def get_context_data(self, **kwargs):
    from content.models import Content
    from events.models import Event
    context = super().get_context_data(**kwargs)
    place, request = self.object, self.request
    editing = is_edit_mode(request) and can_edit(place, request.user)
    sort = get_sort(request, 'place.content', 'added', self.SORTS)
    items = list(
      Content.objects.visible_to(request).listable()
      .filter(Q(places=place) | Q(parts__places=place)).distinct()
      .select_related('photo_detail', 'document_detail', 'book_detail')
      .in_order(sort)
    )
    dated_images = sorted(
      (item for item in items if item.file and item.media_type == 'image' and item.year),
      key=lambda item: (item.year, item.month or 0, item.day or 0),
    )
    context.update({
      'editing': editing,
      'ancestors': place.ancestors()[:-1],
      'items': items,
      'sort': sort,
      'cover': dated_images[0] if dated_images else next((item for item in items if item.file and item.media_type == 'image'), None),
      'events': list(filter_accessible(Event.objects.filter(places=place), request).prefetch_related('people').order_by('year', 'month', 'day')),
      'sub_places': sub_places(place, request, show_all=editing),
      'alternatives': attach_counts(place.alternatives.select_related('parent'), request),
    })
    # Not offered in the picker: what's linked already, and the place itself.
    context['alternative_tokens'] = ','.join([place.token, *(alternative.token for alternative in context['alternatives'])])
    return context
