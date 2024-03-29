from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView

from django.contrib.auth.mixins import PermissionRequiredMixin

from django.urls import reverse

from archive.models import Tag


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
    return context

  def get_queryset(self):
    queryset = Tag.objects.all()
    ''' User filter '''
    if self.request.GET.get('user', False):
      queryset = queryset.filter(user__username__iexact=self.request.GET.get('user', ''))
    ''' Tag search '''
    if self.request.GET.get('search', False):
      search_text = self.request.GET.get('search').lower()
      queryset = queryset.filter(title__icontains=search_text) | \
                 queryset.filter(description__icontains=search_text)
    return queryset

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
    ''' Enforce user upon tag creation '''
    form.instance.user = self.request.user
    return super().form_valid(form)
  
  def get_success_url(self):
    return reverse('archive:tags') + '?mark=' + self.object.slug

class EditTagView(PermissionRequiredMixin, UpdateView):
  model = Tag
  fields = ['title', 'description']
  permission_required = 'archive.change_tag'
  template_name = 'archive/tags/edit.html'
  
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'tags'
    return context