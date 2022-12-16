from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

#from django.urls import reverse, reverse_lazy
#from django.shortcuts import get_object_or_404, redirect

from django.contrib.auth.mixins import PermissionRequiredMixin

from math import floor

from archive.models import Image, Tag


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

class AddTagView(PermissionRequiredMixin, CreateView):
  model = Tag
  fields = ['title', 'description']
  permission_required = 'archive.add_tag'
  template_name = 'archive/tags/edit.html'

  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)

class EditTagView(PermissionRequiredMixin, UpdateView):
  model = Tag
  fields = ['title', 'description']
  permission_required = 'archive.change_tag'
  template_name = 'archive/tags/edit.html'
  # def form_valid(self, form):
  #   return super().form_valid(form)