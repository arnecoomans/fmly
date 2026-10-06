from django import template

register = template.Library()


@register.filter
def relation_to_user(person, request):
  """{{ person|relation_to_user:request }} - a bare {{ person.get_relation_to_user }}
  would call it with request=None (its default), not the real request, since
  Django templates only auto-call a method with no required arguments and
  can't pass one through variable lookup. This filter is the only way to
  actually hand the real request through."""
  return person.get_relation_to_user(request)


@register.filter
def suggested_parents(person, request):
  """{% with suggestions=person|suggested_parents:request %} - with one
  parent known, the likely other parent: [(person, 'partner' | 'co-parent')]
  (people/relatives.py)."""
  from people.relatives import suggested_parents as suggest
  return suggest(person, request)
