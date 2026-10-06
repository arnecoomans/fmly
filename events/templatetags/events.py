from django import template

register = template.Library()


@register.filter
def event_display(event, request):
  """{{ event|event_display:request }} - the event's name as this viewer
  may see it: people they may see by name, the others obfuscated
  (Event.display_for). Use this, never {{ event }} (which names everyone)."""
  return event.display_for(getattr(request, 'user', None))


@register.filter
def age_at_event(person, event):
  """{{ person|age_at_event:event }} -> 'aged 24' / 'about 24' / '' - the
  person's age at the event, from their birth (people/timeline.py age_at).
  Only show it for someone the viewer may see: an age gives away a birth
  date."""
  from people.timeline import age_at
  return age_at(person.birth, event)
