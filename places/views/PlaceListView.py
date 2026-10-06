from django.views.generic import TemplateView

from cmnsd.edit.mode import is_edit_mode

from ..places import place_tree


class PlaceListView(TemplateView):
  """/places/ - the places as a tree (countries, regions, towns), each with
  how many content items and events this viewer may see there
  (places/places.py). Places with nothing there are left out - in edit
  mode every place shows, so all of them can be put in order. Public like
  a place's own page: the counts only include what this viewer may see."""
  template_name = 'place/place_overview.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['show_all'] = is_edit_mode(self.request)
    places = place_tree(self.request, show_all=context['show_all'])
    # Top-level places that hold others get a heading each; the rest
    # (a country with nothing below it) are listed together.
    context['groups'] = [place for place in places if place.listed_children]
    context['loose'] = [place for place in places if not place.listed_children]
    return context
