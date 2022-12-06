from django.views import generic
from django.views.generic.edit import CreateView, DeleteView, UpdateView, FormView

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

from archive.models import Note

# Renamed NoteListView to NotesListView
class NotesListView(generic.ListView):
  model = Note
  context_object_name = 'objects'
  template_name = 'archive/object_list.html'

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['origin'] = 'note'
    context['page_scope'] = 'notities'
    #context['page_description'] = ''
    return context


class NoteView(generic.DetailView):
  model = Note

# Renamed NoteCreateView to AddNoteView
class AddNoteView(generic.edit.CreateView):
  model = Note
  fields = ['title', 'content', 'people', 'tag']
  def form_valid(self, form):
    form.instance.user = self.request.user
    return super().form_valid(form)

# Renamed NoteUpdateView to EditNoteView
class EditNoteView(generic.edit.UpdateView):
  model = Note
  fields = ['title', 'content', 'people', 'tag']