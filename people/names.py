"""Splitting a typed full name into given names and a last name - for a
new person, whose dialog opens with what was typed in a picker
(PersonCreateForm.prepare). A guess, shown in the form to correct.

And initials as a search word (initials_q): "P.W.A.", "p. w. a." or "pwa"
finds Pieter Willem Anthonie - documents name people that way."""
import re

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


# Initials with dots: one letter, or a Dutch two- or three-letter one
# ("Ch.", "Th.", "Joh."), each with its dot - "P.W.A.", "p.w.a.", "Ch.".
_DOTTED = re.compile(r'(?:[A-Za-z][a-z]{0,2}\.)+')
_INITIAL = re.compile(r'([A-Za-z][a-z]{0,2})\.')
# Without dots: one letter per given name - "pwa". Could be any word, so
# only short ones, and they must match all the given names.
_BARE = re.compile(r'[A-Za-z]{2,5}')
# Written like initials, but a title.
TITLES = {'dr', 'drs', 'mr', 'ir', 'ing', 'prof', 'jhr', 'mevr', 'mej', 'wed', 'st', 'jr', 'sr'}

_START = r'(^|[ .-])'      # a given name starts (also after a hyphen: Jan-Willem)
_REST = r'[^ .-]*'         # the rest of it
_BETWEEN = r'[ .-]+'


def initials_pattern(term):
  """A regex (to match case-insensitively) on given_name for a search word
  written as initials, or None:
  - one with a dot ("Ch.", "A."): starts one of the given names - spaced
    initials ("P. W. A.") come one word at a time;
  - several with dots ("P.W.A."): the first given names, in this order -
    later ones may be left out, as documents do;
  - without dots ("pwa"): exactly these given names, one letter each."""
  if _DOTTED.fullmatch(term):
    initials = _INITIAL.findall(term)
    if len(initials) == 1:
      if initials[0].lower() in TITLES:
        return None
      return _START + re.escape(initials[0])
    return '^' + (_REST + _BETWEEN).join(re.escape(initial) for initial in initials)
  if _BARE.fullmatch(term):
    return '^' + (_REST + _BETWEEN).join(re.escape(letter) for letter in term) + _REST + r'[ .]*$'
  return None


def initials_q(term, field='given_name'):
  """The Q for a search word written as initials (initials_pattern), on
  `field` - or an empty Q, which adds nothing to an OR."""
  pattern = initials_pattern(term)
  return Q(**{f'{field}__iregex': pattern}) if pattern else Q()


def matches_initials(person, term):
  """Whether this person's given names explain the search word as initials."""
  pattern = initials_pattern(term)
  return bool(pattern and re.search(pattern, person.given_name or '', re.IGNORECASE))


def _compact(text):
  """Lower case, letters and digits only: "van Dorp" -> "vandorp"."""
  return re.sub(r'[^0-9a-z]', '', (text or '').lower())


def _bare_last(text):
  """A last name without its particles, compact: "van Dorp" -> "dorp"."""
  words = (text or '').lower().split()
  while len(words) > 1 and words[0] in PARTICLES:
    words = words[1:]
  return _compact(' '.join(words))


def likely_people(user, people):
  """The people `user`'s account most likely is - for choosing an
  account's person (core.admin.AccountChangeForm): a suggestion, never a
  choice made. Points per person:
  - the account's first name is their first given name, called name or
    nickname: 3;
  - its last name is their last or married name (case, spaces and
    particles aside: "Dorp" is "van Dorp"): 3;
  - their first or last name is in the email address or username
    ("marindavandorp@…" - an account without names): 1 each.
  Only people whose first name matches one way or the other - a shared
  last name alone is half the family - with at least 2 points (a piece of
  a name inside an address, "lies" in "anneliesdamen", isn't enough on its
  own), and of those only the best score: usually one."""
  first = _compact(user.first_name)
  last = _bare_last(user.last_name)
  handle = _compact((user.email or '').split('@')[0]) + ' ' + _compact(user.get_username().split('@')[0])
  scored = []
  for person in people:
    given = (person.given_name or '').split()
    firsts = {_compact(name) for name in (given[0] if given else '', person.called_name, person.nickname) if name}
    lasts = {_bare_last(name) for name in (person.last_name, person.married_name) if name}
    first_matches = bool(first and first in firsts)
    first_in_handle = any(len(name) >= 3 and name in handle for name in firsts)
    if not (first_matches or first_in_handle):
      continue
    score = 3 * first_matches + 3 * bool(last and last in lasts) + first_in_handle
    score += any(len(name) >= 3 and name in handle for name in lasts)
    scored.append((score, person))
  best = max((score for score, _person in scored), default=0)
  return [person for score, person in scored if score == best] if best >= 2 else []
