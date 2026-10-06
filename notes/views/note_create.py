from django.contrib import messages
from django.contrib.admin.models import ADDITION, LogEntry
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from cmnsd.edit.mode import set_edit_mode
from cmnsd.models.access import filter_accessible

from ..models import Note

# on=<model>:<token> - what a new note starts linked to: the relation on
# Note and the model it holds.
STARTS_ON = {
  'person': ('people', 'people.Person'),
  'content': ('content', 'content.Content'),
  'place': ('places', 'places.Place'),
  'event': ('events', 'events.Event'),
  'tag': ('tags', 'core.Tag'),
  'note': ('related_notes', 'notes.Note'),
}


@require_POST
@login_required
@permission_required('notes.add_note', raise_exception=True)
def note_create(request):
  """POST notes/new/ [on=person:<token>] - a new note: a private draft
  scratch note by this user, linked to what it was started from (a
  person's, item's, place's page - only something the viewer may see),
  opened in edit mode with its title and text forms open (?open=). Nothing is asked first: kind, title
  and text are set on the note's page."""
  from django.apps import apps
  note = Note.objects.create(user=request.user)
  on = request.POST.get('on', '')
  model_name, _sep, token = on.partition(':')
  if model_name in STARTS_ON and token:
    relation, label = STARTS_ON[model_name]
    target = filter_accessible(apps.get_model(label).objects.all(), request).filter(token=token).first()
    if target is not None:
      getattr(note, relation).add(target)
  LogEntry.objects.log_actions(request.user.pk, [note], ADDITION, change_message="Created on the site", single_object=True)
  messages.success(request, _("New note - a draft only you can see until you publish it."))
  try:
    set_edit_mode(request, True)
  except PermissionError:
    # May add, not change: the note shows without its edit controls.
    return redirect(note.get_absolute_url())
  # Title and text open to write in right away (cmnsd.js edit.js ?open=).
  return redirect(f"{note.get_absolute_url()}?open=title,body")
