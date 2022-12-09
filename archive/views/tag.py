from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

from django.urls import reverse, reverse_lazy
from django.shortcuts import get_object_or_404, redirect

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from math import floor

from archive.models import Image, Tag

# # Renamed TagView to ImagesByTagListView
# class ImagesByTagListView(generic.ListView):
#   model = Image
#   context_object_name = 'images'
  
#   def get_context_data(self, **kwargs):
#     context = super().get_context_data(**kwargs)
#     context['page_scope'] = 'documenten met tag "' + self.kwargs['slug'] + '"'
#     #context['page_description'] = ''
#     return context

#   def get_queryset(self):
#     return Image.objects.filter(tag__slug=self.kwargs['slug']).order_by('-uploaded_at')

# Renamed TagsView to TagListView
class TagListView(generic.ListView):
  model = Tag
  template_name = 'archive/tags/list.html'
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['origin'] = 'tag'
    context['page_scope'] = 'tags'
    #context['page_description'] = ''
    return context

class AddTagView(CreateView):
  model = Tag
  fields = ['title']