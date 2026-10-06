from django.views.generic import DetailView

from cmnsd.edit.mode import can_edit, is_edit_mode
from cmnsd.models.access import filter_accessible

from ..models import Note


class NoteDetailView(DetailView):
  """notes/<token>/ - a note: its kind, title, date, confidence and text,
  then what it links to - people, content, places, events, tags, other
  notes - and the notes that link to it. Each linked object only when this
  viewer may see it (a link to a hidden person stays, unseen). A note this
  viewer may not see is a 404, like a missing one.
  In edit mode, for someone with notes.change_note: every field is a block
  (Note.api_edit_forms) and every link list gets its "×" and a picker."""
  model = Note
  slug_field = 'token'
  slug_url_kwarg = 'token'
  context_object_name = 'note'
  template_name = 'note/note_detail.html'

  def get_queryset(self):
    return Note.objects.visible_to(self.request).select_related('user', 'user__person')

  def get_context_data(self, **kwargs):
    from content.models import Content
    context = super().get_context_data(**kwargs)
    note, request = self.object, self.request
    links = {
      'people': list(filter_accessible(note.people.all(), request)),
      'content': list(Content.objects.visible_to(request).filter(notes=note).select_related('photo_detail', 'document_detail')),
      'places': list(note.places.select_related('parent')),
      'events': list(filter_accessible(note.events.all(), request).prefetch_related('people')),
      'tags': list(filter_accessible(note.tags.all(), request)),
      'related_notes': list(Note.objects.visible_to(request).filter(linked_from=note)),
    }
    context['links'] = links
    # Not offered again in a picker: what's linked already (and, for notes,
    # this note itself).
    context['link_tokens'] = {relation: ','.join(obj.token for obj in objects) for relation, objects in links.items()}
    context['link_tokens']['related_notes'] = ','.join([note.token, *(n.token for n in links['related_notes'])])
    context['linked_from'] = list(Note.objects.visible_to(request).filter(related_notes=note))
    context['editing'] = is_edit_mode(request) and can_edit(note, request.user)
    return context
