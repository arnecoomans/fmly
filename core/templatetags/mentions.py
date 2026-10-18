from django import template

register = template.Library()


@register.filter
def mentioned_in(obj, request):
  """{% with rows=person|mentioned_in:request %} - the texts mentioning it
  that this viewer may see (cmnsd.models.Mention.mentioned_in, issue #470):
  [{'source', 'fields', 'kind'}]."""
  from cmnsd.models.Mention import mentioned_in as rows
  return rows(obj, request)
