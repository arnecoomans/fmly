"""
Possible duplicates of a new person (the "already in the archive?" hint
under the names on /people/new/ and in the "+ new person" dialog): the
people this viewer may see whose names hold every word typed - each word
in any of the name fields, as the people search does, but never the
biography. "Willem Bake" finds Willem Johan Alexander Bake; spelling
variants (Baake) are not found. Fewer than MIN_LENGTH letters in all:
nothing yet.
"""

from django.db.models import Q

from cmnsd.models.access import filter_accessible

from .forms import NAME_FIELDS

LIMIT = 5
MIN_LENGTH = 3


def similar_people(request, names):
  """([Person], count) - the first LIMIT matches for `names` ({field:
  text} of the form's name fields), lifespans attached, and how many
  there are."""
  from .models import Person
  words = ' '.join(names.get(field, '') for field in NAME_FIELDS).split()
  if len(''.join(words)) < MIN_LENGTH:
    return [], 0
  people = filter_accessible(Person.objects.all(), request)
  for word in dict.fromkeys(words):
    match = Q()
    for field in NAME_FIELDS:
      match |= Q(**{f'{field}__icontains': word})
    people = people.filter(match)
  people = people.order_by('last_name', 'given_name', 'pk')
  count = people.count()
  shown = list(people[:LIMIT])
  Person._attach_lifespan(shown)
  return shown, count
