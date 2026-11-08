from django import template

from core.sections import split_sections

register = template.Library()


@register.filter
def markdown_sections(text):
  """{% for section in note.body|markdown_sections %} - [(index, text)],
  the text's sections (core/sections.py) - for editing one at a time."""
  return list(enumerate(split_sections(text)))
