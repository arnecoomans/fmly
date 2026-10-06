from collections import Counter

from django.views.generic import ListView

from ..models import Note


class NoteListView(ListView):
  """/notes/ - the notes this viewer may see, open work first (to do,
  questions, hypotheses - Note.KIND_ORDER), each kind newest first; pills
  narrow to one kind (?kind=, in the browser). A draft or private note
  only for its author. "+ New note" for someone who may add notes."""
  template_name = 'note/note_overview.html'
  context_object_name = 'notes'

  def get_queryset(self):
    return Note.objects.visible_to(self.request).in_order().select_related('user')

  def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    counts = Counter(note.kind for note in context['notes'])
    context['kinds'] = [(kind, Note.Kind(kind).label, counts[kind]) for kind in Note.KIND_ORDER if counts[kind]]
    return context
