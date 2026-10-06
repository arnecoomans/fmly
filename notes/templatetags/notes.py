from django import template

register = template.Library()


@register.filter
def visible_notes(obj, request):
  """{% with notes=person|visible_notes:request %} - the notes linked to a
  person, item, place, event or tag that this viewer may see, open work
  first (Note.objects.visible_to, in_order)."""
  return list(obj.notes.visible_to(request).in_order())


@register.filter
def note_target(obj):
  """{{ person|note_target }} -> 'person:<token>' - what a new note started
  from this page is linked to (notes.views.note_create, `on`)."""
  return f'{obj._meta.model_name}:{obj.token}'
