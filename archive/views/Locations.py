from django.views.generic import ListView
from django.conf import settings

from archive.models import Location

from cmnsd.mixins import FilterMixin

class LocationListView(FilterMixin, ListView):
  model = Location

  def get_queryset(self):
    queryset = super().get_queryset()
    queryset = self.filter(queryset)
    return queryset.order_by('parent__parent__name', 'parent__name', 'name')