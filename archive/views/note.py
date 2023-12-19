from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from archive.models import Note

''' Notes List View'''
class NotesListView(ListView):
  model = Note
  template_name = 'archive/notes/list.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'notes'
    return context

  def get_queryset(self):
    queryset = Note.objects.all()
    ''' User filter '''
    if self.request.GET.get('user', False):
      queryset = queryset.filter(user__username__iexact=self.request.GET.get('user', ''))
    ''' Note search '''
    if self.request.GET.get('search'):
      search_text = self.request.GET.get('search').lower()
      queryset = queryset.filter(title__icontains=search_text) | \
                 queryset.filter(content__icontains=search_text)
    return queryset
''' Note Detail View'''
class NoteView(DetailView):
  model = Note
  template_name = 'archive/notes/detail.html'
  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'notes'
    return context

''' Add Note View'''
class AddNoteView(PermissionRequiredMixin, CreateView):
  model = Note
  template_name = 'archive/notes/edit.html'
  fields = ['title', 'content', 'images', 'people', 'tags', 'attachments']
  permission_required = 'archive.add_note'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'notes'
    return context

  def form_valid(self, form):
    ''' Enforce note user is current user '''
    form.instance.user = self.request.user
    return super().form_valid(form)

''' Edit Note View '''
class EditNoteView(PermissionRequiredMixin, UpdateView):
  model = Note
  template_name = 'archive/notes/edit.html'
  fields = ['title', 'content', 'images', 'people', 'tags', 'attachments']
  permission_required = 'archive.change_note'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['active_page'] = 'notes'
    return context

  def form_valid(self, form):
    messages.add_message(self.request, messages.SUCCESS, f"Notitie \"{form.instance.title}\" opgeslagen.")
    return super().form_valid(form)