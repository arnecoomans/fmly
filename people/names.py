"""Splitting a typed full name into given names and a last name - for a
new person, whose dialog opens with what was typed in a picker
(PersonCreateForm.prepare). A guess, shown in the form to correct."""
from django.db.models import Q

# Words that start a last name (Dutch, German, French): "van der Wall".
PARTICLES = {'van', 'de', 'der', 'den', 'ter', 'ten', 'te', "'t", 'in', 'op', 'uit', 'von', 'zu', 'du', 'la', 'le'}


def split_name(text, people):
  """(given names, last name) from `text`. The first rule that fits:
  1. its longest ending that is a last or married name of one of `people`
     (only those the viewer may see) - at least one given name stays;
  2. a particle after the first word starts the last name;
  3. the last word. A single word is a given name."""
  words = text.split()
  if len(words) < 2:
    return text.strip(), ''
  endings = [' '.join(words[i:]) for i in range(1, len(words))]   # longest first
  query = Q()
  for ending in endings:
    query |= Q(last_name__iexact=ending) | Q(married_name__iexact=ending)
  known = {name.lower() for pair in people.filter(query).values_list('last_name', 'married_name') for name in pair if name}
  for i, ending in enumerate(endings, start=1):
    if ending.lower() in known:
      return ' '.join(words[:i]), ending
  for i in range(1, len(words)):
    if words[i].lower() in PARTICLES:
      return ' '.join(words[:i]), ' '.join(words[i:])
  return ' '.join(words[:-1]), words[-1]
