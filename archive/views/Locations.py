from django.views.generic import DetailView, ListView, TemplateView
from django.views.generic.edit import CreateView, UpdateView
from django.shortcuts import redirect
from django.conf import settings
from django.contrib import messages
from django.urls import reverse
from django.utils.translation import gettext as _

from django.contrib.auth.mixins import PermissionRequiredMixin

from archive.models import Location

from cmnsd.views.cmnsd_filter import FilterMixin

class LocationListView(FilterMixin, ListView):
  model = Location

  def get_queryset(self):
    queryset = super().get_queryset()
    queryset = self.filter(queryset)
    return queryset.order_by('parent__parent__name', 'parent__name', 'name')