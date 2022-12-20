from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView

from django.contrib.auth.mixins import PermissionRequiredMixin

from math import floor

from archive.models import Image, Tag


''' Tags
    Tags are referenced in images, groups and attachments and are used to add context.
    Tag detail view is handled by the Image model, where it displays all images with a set tag.
'''
class TagListView(ListView):
  model = Tag
  template_name = 'archive/tags/list.html'
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'tags'
    # context['origin'] = 'tag'
    # context['page_scope'] = 'tags'
    return context

class AddTagView(PermissionRequiredMixin, CreateView):
  model = Tag
  fields = ['title', 'description']
  permission_required = 'archive.add_tag'
  template_name = 'archive/tags/edit.html'
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'tags'
    return context
  
  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)

class EditTagView(PermissionRequiredMixin, UpdateView):
  model = Tag
  fields = ['title', 'description']
  permission_required = 'archive.change_tag'
  template_name = 'archive/tags/edit.html'
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'tags'
    return context