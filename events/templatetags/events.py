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


# A blank line ends a paragraph (Markdown) - spaces on it too, and a
# browser's line endings (\r\n: a textarea's, as stored).
_PARAGRAPH_BREAK = __import__('re').compile(r'\r?\n[ \t\r]*\r?\n')


@register.filter
def first_paragraph(text):
  """The text up to its first blank line - an event row's excerpt
  (event/_event.html): the writer's own split, not a count of words; the
  rest on the event's page ("read more"). Single line breaks stay - they're
  within the paragraph."""
  return _PARAGRAPH_BREAK.split((text or '').strip(), maxsplit=1)[0]


@register.filter
def has_more_paragraphs(text):
  """Whether the text goes on after its first paragraph."""
  return len(_PARAGRAPH_BREAK.split((text or '').strip(), maxsplit=1)) > 1
