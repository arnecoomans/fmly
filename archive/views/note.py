from django.views.generic import ListView, DetailView
from django.views.generic.edit import CreateView, UpdateView
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from archive.models import Note

# Renamed NoteListView to NotesListView
class NotesListView(ListView):
  model = Note
  template_name = 'archive/notes/list.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['origin'] = 'note'
    context['page_scope'] = 'notities'
    #context['page_description'] = ''
    return context


class NoteView(DetailView):
  model = Note
  template_name = 'archive/notes/detail.html'

# Renamed NoteCreateView to AddNoteView
class AddNoteView(PermissionRequiredMixin, CreateView):
  model = Note
  template_name = 'archive/notes/edit.html'
  fields = ['title', 'content', 'people', 'tag']
  permission_required = 'archive.add_note'

  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)

# Renamed NoteUpdateView to EditNoteView
class EditNoteView(PermissionRequiredMixin, UpdateView):
  model = Note
  template_name = 'archive/notes/edit.html'
  fields = ['title', 'content', 'people', 'tag']
  permission_required = 'archive.change_note'

  def form_valid(self, form):
    messages.add_message(self.request, messages.SUCCESS, f"Notitie \"{form.instance.title}\" opgeslagen.")
    return super().form_valid(form)