from django.db.models import Prefetch
from django.views.generic import DetailView

from cmnsd.edit.mode import can_edit, is_edit_mode
from cmnsd.models.access import filter_accessible

from ..models import Event


class EventDetailView(DetailView):
  """events/<token>/ - an event: what, when, who, where, what happened (the
  description and its sources), the items documenting it and the notes
  about it - only what this viewer may see. Visible like the event itself:
  through its people; a historical event, without people, to everyone. A
  deleted event is gone (404).
  In edit mode, for someone with events.change_event: the blocks
  (Event.api_edit_forms) and pickers for its people, places and items
  (EditableRelationsMixin)."""
  model = Event
  slug_field = 'token'
  slug_url_kwarg = 'token'
  context_object_name = 'event'
  template_name = 'event/event_detail.html'

  def get_queryset(self):
    return filter_accessible(Event.objects.all(), self.request)

  def get_object(self, queryset=None):
    from content.models import Content
    event = super().get_object(queryset)
    # The page's lists, as this viewer may see them.
    event.visible_content = list(Content.objects.visible_to(self.request).filter(events=event))
    return event

  def get_context_data(self, **kwargs):
    from people.models import Person
    context = super().get_context_data(**kwargs)
    event, request = self.object, self.request
    # Everyone, as rows - a person this viewer may not see is shown
    # obfuscated (people/_person_row.html), as on the event cards.
    people = Person._attach_portraits(Person._attach_lifespan(event.people.all()))
    context.update({
      'editing': is_edit_mode(request) and can_edit(event, request.user),
      'people': people,
      'places': list(event.places.select_related('parent')),
    })
    context['tokens'] = {
      'people': ','.join(p.token for p in people),
      'places': ','.join(p.token for p in context['places']),
      'content': ','.join(item.token for item in event.visible_content),
    }
    return context
